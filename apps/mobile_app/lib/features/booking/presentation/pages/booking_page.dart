import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/shell_navigation.dart';
import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/network/idempotency.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/custom_text_field.dart';
import '../../../profile/data/address_api.dart';
import '../../../profile/presentation/pages/addresses_page.dart';
import '../../../services/domain/entities/service_entity.dart';
import '../../domain/entities/booking.dart';
import '../../data/availability_api.dart';
import '../../data/coupon_api.dart';
import '../bloc/booking_bloc.dart';
import '../bloc/booking_event.dart';
import '../bloc/booking_state.dart';

/// The days on offer and, for a shop that hasn't published opening hours, its start times.
///
/// A shop with hours gets its times from booking_service (AvailabilityApi). One without them takes any
/// future time, so it is offered every half hour from 9 AM to 8 PM, the usual working hours, at least
/// [leadTime] from now; the shop confirms or declines each request.
class BookingSlots {
  static const firstHour = 9, lastHour = 20;
  static const days = 14;
  static const leadTime = Duration(minutes: 30);

  /// Start times on [day] still open after [now], for a shop without opening hours.
  static List<DateTime> on(DateTime day, {required DateTime now}) {
    final earliest = now.add(leadTime);
    return [
      for (var minutes = firstHour * 60; minutes <= lastHour * 60; minutes += 30)
        DateTime(day.year, day.month, day.day, minutes ~/ 60, minutes % 60),
    ].where((t) => !t.isBefore(earliest)).toList();
  }

  /// Today and the [days] - 1 days after it (booking_service shows times up to two weeks ahead).
  static List<DateTime> upcomingDays({required DateTime now}) =>
      [for (var i = 0; i < days; i++) DateTime(now.year, now.month, now.day + i)];
}

/// A start time on offer: [shown] is the shop's wall-clock time on the chosen day, [at] the instant booked.
class _Slot {
  final DateTime shown;
  final DateTime at;

  const _Slot(this.shown, this.at);

  @override
  bool operator ==(Object other) => other is _Slot && other.at == at;

  @override
  int get hashCode => at.hashCode;
}

class BookingPage extends StatefulWidget {
  final String serviceId;
  final String serviceName;
  final double servicePrice;
  final CouponApi? couponApi;
  final AddressApi? addressApi;
  final AvailabilityApi? availabilityApi;

  /// The ways the service is offered (ServiceMode values) and their extra fees.
  final List<String> serviceModes;
  final double homeVisitFee;
  final double pickupFee;

  /// The current time (replaceable in tests).
  final DateTime Function() clock;

  const BookingPage({
    super.key,
    required this.serviceId,
    required this.serviceName,
    required this.servicePrice,
    this.couponApi,
    this.addressApi,
    this.availabilityApi,
    this.serviceModes = const [ServiceMode.atShop],
    this.homeVisitFee = 0,
    this.pickupFee = 0,
    this.clock = DateTime.now,
  });

  @override
  State<BookingPage> createState() => _BookingPageState();
}

class _BookingPageState extends State<BookingPage> {
  final _formKey = GlobalKey<FormState>();
  final _notesController = TextEditingController();
  final _couponController = TextEditingController();
  final _itemController = TextEditingController();
  late final AddressApi _addressApi = widget.addressApi ?? sl<AddressApi>();
  late final AvailabilityApi _availabilityApi = widget.availabilityApi ?? sl<AvailabilityApi>();
  CouponCheck? _coupon;
  List<SavedAddress> _saved = const [];
  bool _addressesLoaded = false;
  late String _mode = widget.serviceModes.isEmpty ? ServiceMode.atShop : widget.serviceModes.first;
  SavedAddress? _address;
  bool _checkingCoupon = false;
  late final List<DateTime> _days = BookingSlots.upcomingDays(now: widget.clock());
  late DateTime _day = _days.first;
  _Slot? _slot;
  // Each day's times as booking_service reported them, the days being fetched, and those that failed.
  final Map<DateTime, DayAvailability> _availability = {};
  final Set<DateTime> _loadingDays = {};
  final Map<DateTime, Object> _failedDays = {};
  // The time of day picked before switching days, kept if the new day offers it too.
  (int, int)? _wantedTime;
  // Shown under the schedule / address once the customer tries to book without them.
  bool _showMissing = false;
  final _whenKey = GlobalKey(), _addressKey = GlobalKey(), _itemKey = GlobalKey();
  // One key per booking attempt. Tapping again after an error sends the same request with the same key,
  // so if the first try did reach the server it hands back that booking instead of making a second one;
  // changing any detail is a new attempt with a new key.
  String? _attemptKey;
  List<Object?>? _attemptDetails;

  @override
  void initState() {
    super.initState();
    _loadAddresses();
    _loadTimes(_day);
  }

  Future<void> _loadTimes(DateTime day, {bool refresh = false}) async {
    if (!refresh && (_availability.containsKey(day) || _loadingDays.contains(day))) return;
    setState(() {
      _loadingDays.add(day);
      _failedDays.remove(day);
      if (refresh) _availability.remove(day);
    });
    try {
      final times = await _availabilityApi.forDay(widget.serviceId, day);
      if (!mounted) return;
      setState(() {
        _availability[day] = times;
        if (day == _day) _keepSlotIfOffered();
      });
    } catch (e) {
      if (mounted) setState(() => _failedDays[day] = e);
    } finally {
      if (mounted) setState(() => _loadingDays.remove(day));
    }
  }

  /// The times on offer on [day], or null until they are known.
  List<_Slot>? _slotsOn(DateTime day) {
    final times = _availability[day];
    if (times == null) return null;
    if (!times.hoursConfigured) {
      return [for (final t in BookingSlots.on(day, now: widget.clock())) _Slot(t, t)];
    }
    return [for (final s in times.slots) _Slot(DateTime(day.year, day.month, day.day, s.hour, s.minute), s.at)];
  }

  /// Why [day] has no times, in the customer's words.
  String _noTimesMessage(DateTime day) {
    final times = _availability[day];
    if (times == null || !times.hoursConfigured) return 'No more times today — try another day';
    return switch (times.status) {
      DayStatus.closed => 'Closed on this day',
      DayStatus.holiday => times.holidayNote == null ? 'Closed on this day' : 'Closed on this day (${times.holidayNote})',
      DayStatus.fullyBooked => 'Fully booked — try another day',
      DayStatus.noMoreToday => 'No more times today — try another day',
      _ => times.message ?? 'No times on this day — try another day',
    };
  }

  /// Once the chosen day's times are known: drops a picked time that is no longer offered, and on a new
  /// day picks the same time of day if it is there.
  void _keepSlotIfOffered() {
    final slots = _slotsOn(_day);
    if (slots == null) return;
    if (_slot != null && !slots.contains(_slot)) _slot = null;
    final wanted = _wantedTime;
    if (_slot == null && wanted != null) {
      _slot = slots.where((s) => s.shown.hour == wanted.$1 && s.shown.minute == wanted.$2).firstOrNull;
    }
    _wantedTime = null;
  }

  void _chooseDay(DateTime day) {
    setState(() {
      if (_slot != null) _wantedTime = (_slot!.shown.hour, _slot!.shown.minute);
      _slot = null;
      _day = day;
      _keepSlotIfOffered();
    });
    _loadTimes(day);
  }

  Future<void> _loadAddresses() async {
    try {
      final saved = await _addressApi.list();
      if (!mounted) return;
      setState(() {
        _saved = saved;
        _address ??= saved.isEmpty ? null : saved.first; // the default address comes first
      });
    } catch (_) {
      // Shown as "no saved address" with a way to add one.
    } finally {
      if (mounted) setState(() => _addressesLoaded = true);
    }
  }

  Future<void> _addAddress() async {
    final added = await addAddress(context, _addressApi);
    if (added == null || !mounted) return;
    setState(() {
      _saved = [..._saved, added];
      _address = added;
    });
  }

  @override
  void dispose() {
    _notesController.dispose();
    _couponController.dispose();
    _itemController.dispose();
    super.dispose();
  }

  Future<void> _applyCoupon() async {
    final code = _couponController.text.trim().toUpperCase();
    if (code.isEmpty) return setState(() => _coupon = null);
    FocusScope.of(context).unfocus();
    setState(() => _checkingCoupon = true);
    try {
      final check = await (widget.couponApi ?? sl<CouponApi>()).check(code);
      if (mounted) setState(() => _coupon = check);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _checkingCoupon = false);
    }
  }

  void _removeCoupon() => setState(() {
        _coupon = null;
        _couponController.clear();
      });

  bool get _needsAddress => ServiceMode.needsAddress.contains(_mode);

  double _feeFor(String mode) => switch (mode) {
        ServiceMode.atHome => widget.homeVisitFee,
        ServiceMode.pickupDrop => widget.pickupFee,
        _ => 0,
      };

  double get _fee => _feeFor(_mode);

  bool get _couponApplies => _coupon?.isValid ?? false;

  /// The coupon discounts the service; the visit or pickup fee is added on top (as booking_service prices it).
  double get _discount => _couponApplies ? widget.servicePrice * _coupon!.discountPct / 100 : 0;

  double get _price => widget.servicePrice - _discount + _fee;

  void _onBook() {
    if (context.read<BookingBloc>().state is BookingLoading) return; // already sending
    final formOk = _formKey.currentState?.validate() ?? false;
    final slot = _slot;
    final addressMissing = _needsAddress && _address == null;
    if (!formOk || slot == null || addressMissing) {
      setState(() => _showMissing = true);
      // Bring the first thing to fix into view; it may be far up or down the form.
      final target = slot == null ? _whenKey : addressMissing ? _addressKey : _itemKey;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final ctx = target.currentContext;
        if (ctx != null) Scrollable.ensureVisible(ctx, duration: const Duration(milliseconds: 300), alignment: 0.1);
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(slot == null
              ? 'Pick a time for your booking'
              : addressMissing
                  ? 'Add the address we should come to'
                  : 'Please fill in the highlighted details'),
        ),
      );
      return;
    }
    // At the shop nobody comes to the customer, so no address goes with it.
    final address = _needsAddress ? _address!.oneLine : '';
    final notes = _notesController.text.trim().isEmpty ? null : _notesController.text.trim();
    // Only a code that checked out is sent; the server applies it to the catalogue price.
    final couponCode = _couponApplies ? _coupon!.code : null;
    final delivery = BookingDelivery(
      mode: _mode,
      addressId: _needsAddress ? _address!.id : null,
      itemDescription: _mode == ServiceMode.pickupDrop ? _itemController.text.trim() : null,
    );
    final details = <Object?>[slot.at, address, notes, couponCode, delivery];
    if (_attemptKey == null || !listEquals(details, _attemptDetails)) {
      _attemptKey = newIdempotencyKey();
      _attemptDetails = details;
    }
    context.read<BookingBloc>().add(
          CreateBookingRequested(
            serviceId: widget.serviceId,
            scheduledAt: slot.at,
            address: address,
            notes: notes,
            couponCode: couponCode,
            delivery: delivery,
            idempotencyKey: _attemptKey,
          ),
        );
  }

  Future<void> _showBooked(Booking booking) async {
    final navigator = Navigator.of(context);
    final viewBookings = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        icon: Icon(Icons.check_circle, color: context.palette.success, size: 56),
        title: const Text('Booking requested'),
        content: Text(
          '${widget.serviceName}\n${friendlyDateTime(booking.scheduledAt)}'
          '${booking.bookingNumber.isEmpty ? '' : '\nBooking #${booking.bookingNumber}'}\n\n'
          "The shop will confirm it shortly. We'll notify you, and you can pay once it's confirmed.",
          textAlign: TextAlign.center,
        ),
        actionsAlignment: MainAxisAlignment.center,
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Done')),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('View my bookings')),
        ],
      ),
    );
    if (!mounted) return;
    if (viewBookings == true) {
      ShellNavigation.show(context, ShellTab.bookings);
    } else {
      navigator.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final slots = _slotsOn(_day);
    return BlocListener<BookingBloc, BookingState>(
      listener: (context, state) {
        if (state is BookingCreated) {
          _showBooked(state.booking);
        } else if (state is BookingError) {
          // The time may just have been taken (or the shop's hours changed): show what is free now.
          if (_availability[_day]?.hoursConfigured ?? false) _loadTimes(_day, refresh: true);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(state.message),
              backgroundColor: AppColors.error,
            ),
          );
        }
      },
      child: Scaffold(
        appBar: AppBar(title: const Text('Book Service')),
        bottomNavigationBar: _BookBar(total: _price, onBook: _onBook),
        body: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SummaryCard(serviceName: widget.serviceName, mode: _mode, slot: _slot?.shown, now: widget.clock()),
                const SizedBox(height: 24),
                if (widget.serviceModes.length > 1) ...[
                  const _Heading('How would you like it?'),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final mode in widget.serviceModes)
                        ChoiceChip(
                          avatar: Icon(modeIcon(mode), size: 18),
                          showCheckmark: false,
                          label: Text(modeChoiceLabel(mode, _feeFor(mode))),
                          selected: _mode == mode,
                          onSelected: (_) => setState(() => _mode = mode),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(modeExplanation(_mode), style: AppTextStyles.caption.themed(context)),
                  const SizedBox(height: 24),
                ],
                _Heading('When?', key: _whenKey),
                SizedBox(
                  height: 64,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: _days.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 8),
                    itemBuilder: (context, i) {
                      final day = _days[i];
                      final selected = day == _day;
                      return _DayChip(
                        day: day,
                        now: widget.clock(),
                        selected: selected,
                        onTap: () => _chooseDay(day),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 12),
                if (slots == null && _failedDays.containsKey(_day))
                  _TimesProblem(
                    text: "Couldn't load the times for this day",
                    action: TextButton.icon(
                      onPressed: () => _loadTimes(_day, refresh: true),
                      icon: const Icon(Icons.refresh, size: 18),
                      label: const Text('Retry'),
                    ),
                  )
                else if (slots == null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Row(
                      children: [
                        const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                        const SizedBox(width: 12),
                        Flexible(child: Text('Finding free times…', style: AppTextStyles.body2.themed(context))),
                      ],
                    ),
                  )
                else if (slots.isEmpty)
                  _TimesProblem(text: _noTimesMessage(_day)),
                // Grouped by part of the day so 20-odd times are quick to scan.
                for (final (part, times) in [
                  ('Morning', (slots ?? const <_Slot>[]).where((t) => t.shown.hour < 12)),
                  ('Afternoon', (slots ?? const <_Slot>[]).where((t) => t.shown.hour >= 12 && t.shown.hour < 17)),
                  ('Evening', (slots ?? const <_Slot>[]).where((t) => t.shown.hour >= 17)),
                ])
                  if (times.isNotEmpty) ...[
                    Padding(
                      padding: const EdgeInsets.only(top: 4, bottom: 6),
                      child: Text(part, style: AppTextStyles.caption.themed(context)),
                    ),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final t in times)
                          ChoiceChip(
                            label: Text(clockTime(t.shown)),
                            showCheckmark: false,
                            selected: _slot == t,
                            onSelected: (_) => setState(() => _slot = t),
                          ),
                      ],
                    ),
                    const SizedBox(height: 8),
                  ],
                if (_showMissing && _slot == null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text('Pick a time', style: AppTextStyles.caption.copyWith(color: context.colors.error)),
                  ),
                const SizedBox(height: 24),
                if (_needsAddress) ...[
                  _Heading(_mode == ServiceMode.pickupDrop ? 'Collect from' : 'Where should we come?', key: _addressKey),
                  if (!_addressesLoaded)
                    const LinearProgressIndicator()
                  else if (_saved.isEmpty)
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        border: Border.all(color: _showMissing ? context.colors.error : context.colors.outlineVariant),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('You have no saved address yet.', style: AppTextStyles.body2.themed(context)),
                          const SizedBox(height: 8),
                          OutlinedButton.icon(
                            onPressed: _addAddress,
                            icon: const Icon(Icons.add_location_alt_outlined),
                            label: const Text('Add address'),
                          ),
                        ],
                      ),
                    )
                  else ...[
                    DropdownButtonFormField<SavedAddress>(
                      initialValue: _address,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Saved address'),
                      items: [
                        for (final a in _saved)
                          DropdownMenuItem(value: a, child: Text('${a.label}: ${a.oneLine}', overflow: TextOverflow.ellipsis)),
                      ],
                      onChanged: (a) => setState(() => _address = a),
                    ),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: _addAddress,
                        icon: const Icon(Icons.add, size: 18),
                        label: const Text('Add another address'),
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                ],
                if (_mode == ServiceMode.pickupDrop) ...[
                  CustomTextField(
                    key: _itemKey,
                    controller: _itemController,
                    label: 'What should we collect?',
                    hint: 'e.g. Honda Activa, brakes squeaking · Dell laptop, cracked screen',
                    maxLines: 2,
                    textCapitalization: TextCapitalization.sentences,
                    validator: (v) => (v == null || v.trim().isEmpty) ? 'Tell us what to collect and what is wrong' : null,
                  ),
                  const SizedBox(height: 16),
                ],
                CustomTextField(
                  controller: _notesController,
                  label: 'Notes (optional)',
                  hint: 'Any special instructions...',
                  maxLines: 2,
                  textCapitalization: TextCapitalization.sentences,
                ),
                const SizedBox(height: 16),
                if (_couponApplies)
                  _AppliedCoupon(coupon: _coupon!, saving: _discount, onRemove: _removeCoupon)
                else ...[
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: CustomTextField(
                          controller: _couponController,
                          label: 'Coupon code (optional)',
                          hint: 'e.g. WELCOME10',
                          textCapitalization: TextCapitalization.characters,
                          textInputAction: TextInputAction.done,
                          onSubmitted: (_) => _applyCoupon(),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Padding(
                        padding: const EdgeInsets.only(top: 28),
                        child: TextButton(
                          onPressed: _checkingCoupon ? null : _applyCoupon,
                          child: Text(_checkingCoupon ? 'Checking…' : 'Apply'),
                        ),
                      ),
                    ],
                  ),
                  if (_coupon != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(_coupon!.message, style: AppTextStyles.caption.copyWith(color: context.colors.error)),
                    ),
                ],
                const SizedBox(height: 24),
                _PriceBreakdown(
                  service: widget.servicePrice,
                  feeLabel: _mode == ServiceMode.atHome ? 'Home visit fee' : 'Pickup & drop fee',
                  fee: _fee,
                  couponCode: _couponApplies ? _coupon!.code : null,
                  discount: _discount,
                  total: _price,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Why there are no times to pick (closed, fully booked, or they could not be loaded), with what to do.
class _TimesProblem extends StatelessWidget {
  final String text;
  final Widget? action;

  const _TimesProblem({required this.text, this.action});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
        margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(
          color: context.colors.surface,
          border: Border.all(color: context.colors.outlineVariant),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.event_busy_outlined, size: 20, color: context.palette.muted),
                const SizedBox(width: 8),
                Expanded(child: Text(text, style: AppTextStyles.body2.themed(context))),
              ],
            ),
            if (action != null) action! else const SizedBox(height: 8),
          ],
        ),
      );
}

class _Heading extends StatelessWidget {
  final String text;

  const _Heading(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Semantics(header: true, child: Text(text, style: AppTextStyles.subtitle1)),
      );
}

class _DayChip extends StatelessWidget {
  final DateTime day;
  final DateTime now;
  final bool selected;
  final VoidCallback onTap;

  const _DayChip({required this.day, required this.now, required this.selected, required this.onTap});

  static const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  static const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  @override
  Widget build(BuildContext context) {
    final relative = friendlyDay(day, now: now);
    final top = relative == 'Today' || relative == 'Tomorrow' ? relative : _weekdays[day.weekday - 1];
    return Semantics(
      button: true,
      selected: selected,
      label: relative == top ? '$top, ${day.day} ${_months[day.month - 1]}' : relative,
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          width: 72,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: selected ? context.colors.primaryContainer : context.colors.surface,
            border: Border.all(color: selected ? context.colors.primary : context.colors.outlineVariant, width: selected ? 2 : 1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(top, style: AppTextStyles.caption.copyWith(color: selected ? context.colors.onPrimaryContainer : context.palette.muted)),
                Text(
                  '${day.day} ${_months[day.month - 1]}',
                  style: AppTextStyles.subtitle2.copyWith(color: selected ? context.colors.onPrimaryContainer : context.colors.onSurface),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _AppliedCoupon extends StatelessWidget {
  final CouponCheck coupon;
  final double saving;
  final VoidCallback onRemove;

  const _AppliedCoupon({required this.coupon, required this.saving, required this.onRemove});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(12, 4, 4, 4),
        decoration: BoxDecoration(
          color: context.palette.success.withValues(alpha: 0.08),
          border: Border.all(color: context.palette.success.withValues(alpha: 0.4)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Icon(Icons.local_offer_outlined, color: context.palette.success, size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '${coupon.code} applied: ${coupon.discountPct.toStringAsFixed(coupon.discountPct % 1 == 0 ? 0 : 1)}% off, '
                'you save ${rupees(saving)}',
                style: AppTextStyles.body2.copyWith(color: context.palette.success),
              ),
            ),
            TextButton(onPressed: onRemove, child: const Text('Remove')),
          ],
        ),
      );
}

class _PriceBreakdown extends StatelessWidget {
  final double service;
  final String feeLabel;
  final double fee;
  final String? couponCode;
  final double discount;
  final double total;

  const _PriceBreakdown({
    required this.service,
    required this.feeLabel,
    required this.fee,
    required this.couponCode,
    required this.discount,
    required this.total,
  });

  Widget _row(BuildContext context, String label, String amount, {TextStyle? style}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(
          children: [
            Expanded(child: Text(label, style: style ?? AppTextStyles.body2.themed(context))),
            Text(amount, style: style ?? AppTextStyles.body2.themed(context)),
          ],
        ),
      );

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: context.colors.surface,
          border: Border.all(color: context.colors.outlineVariant),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Heading('Price details'),
            _row(context, 'Service', rupees(service)),
            if (fee > 0) _row(context, feeLabel, rupees(fee)),
            if (discount > 0) _row(context, 'Coupon $couponCode', '−${rupees(discount)}', style: AppTextStyles.body2.copyWith(color: context.palette.success)),
            const Divider(height: 16),
            _row(context, 'Total', rupees(total), style: AppTextStyles.subtitle1),
            const SizedBox(height: 4),
            Text(
              'Nothing to pay now. Pay online or in cash once the shop confirms.',
              style: AppTextStyles.caption.themed(context),
            ),
          ],
        ),
      );
}

/// Stays at the bottom: the total and the button, so the customer never has to scroll to book.
class _BookBar extends StatelessWidget {
  final double total;
  final VoidCallback onBook;

  const _BookBar({required this.total, required this.onBook});

  @override
  Widget build(BuildContext context) => Material(
        color: context.colors.surface,
        elevation: 8,
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
            child: Row(
              children: [
                Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Total', style: AppTextStyles.caption.themed(context)),
                    Text(rupees(total), style: AppTextStyles.heading3.copyWith(color: context.colors.primary)),
                  ],
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: BlocBuilder<BookingBloc, BookingState>(
                    builder: (context, state) => CustomButton(
                      label: 'Confirm Booking',
                      onPressed: state is BookingLoading ? null : onBook,
                      isLoading: state is BookingLoading,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
}

class _SummaryCard extends StatelessWidget {
  final String serviceName;
  final String mode;
  final DateTime? slot;
  final DateTime now;

  const _SummaryCard({required this.serviceName, required this.mode, required this.slot, required this.now});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.primaryContainer,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(modeIcon(mode), color: context.colors.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(serviceName, style: AppTextStyles.subtitle1),
                Text(
                  slot == null ? 'Choose a day and time below' : friendlyDateTime(slot!, now: now),
                  style: AppTextStyles.body2.copyWith(color: context.colors.onPrimaryContainer),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

IconData modeIcon(String mode) => switch (mode) {
      ServiceMode.atHome => Icons.home_outlined,
      ServiceMode.pickupDrop => Icons.local_shipping_outlined,
      _ => Icons.storefront_outlined,
    };

/// "Visit the shop", "At my place (+₹150)", "Pickup & drop (+₹99)".
String modeChoiceLabel(String mode, double fee) {
  final name = switch (mode) {
    ServiceMode.atHome => 'At my place',
    ServiceMode.pickupDrop => 'Pickup & drop',
    _ => 'Visit the shop',
  };
  return fee > 0 ? '$name (+${rupees(fee)})' : name;
}

String modeExplanation(String mode) => switch (mode) {
      ServiceMode.atHome => 'A professional comes to your address at the time you choose.',
      ServiceMode.pickupDrop => "We collect your item from your address, service it and bring it back. You'll be told at each step.",
      _ => 'You go to the shop at the time you choose. See "How to get there" on your booking.',
    };
