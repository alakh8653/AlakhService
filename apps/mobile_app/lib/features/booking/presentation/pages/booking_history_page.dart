import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../directions/presentation/how_to_get_there_sheet.dart';
import '../../../payment/data/payment_api.dart';
import '../../../payment/presentation/pages/payment_page.dart';
import '../../../tracking/presentation/pages/live_tracking_page.dart';
import '../../data/dispute_api.dart';
import '../../data/rating_api.dart';
import '../../domain/entities/booking.dart';
import '../bloc/booking_bloc.dart';
import '../bloc/booking_event.dart';
import '../bloc/booking_state.dart';

class BookingHistoryPage extends StatefulWidget {
  /// Takes the customer to the catalogue (from the empty list).
  final VoidCallback? onBrowseServices;
  final PaymentApi? paymentApi;
  final RatingApi? ratingApi;
  final DisputeApi? disputeApi;

  const BookingHistoryPage({super.key, this.onBrowseServices, this.paymentApi, this.ratingApi, this.disputeApi});

  @override
  State<BookingHistoryPage> createState() => _BookingHistoryPageState();
}

class _BookingHistoryPageState extends State<BookingHistoryPage> {
  // booking id → 'paid' or 'cash' (to pay in person), so a paid booking isn't offered for payment again.
  Map<String, String> _payments = const {};
  // Bookings rated on this screen (a booking can be rated once), with the stars given.
  final Map<String, int> _rated = {};
  // The booking being cancelled, so its button can't be tapped twice.
  String? _cancelling;

  PaymentApi get _paymentApi => widget.paymentApi ?? sl<PaymentApi>();

  @override
  void initState() {
    super.initState();
    context.read<BookingBloc>().add(const LoadUserBookings());
    _loadPayments();
  }

  Future<void> _loadPayments() async {
    try {
      final states = await _paymentApi.paymentStateByBooking();
      if (mounted) setState(() => _payments = states);
    } catch (_) {
      // Without it the Pay button stays; the server still refuses a second payment.
    }
  }

  static Color statusColor(String status) => switch (status) {
        BookingStatus.confirmed || BookingStatus.assigned => AppColors.info,
        BookingStatus.enRoute || BookingStatus.pickedUp || BookingStatus.inProgress || BookingStatus.outForDelivery => AppColors.primary,
        BookingStatus.completed => AppColors.success,
        BookingStatus.pending => AppColors.warning,
        BookingStatus.cancelled || BookingStatus.disputed => AppColors.error,
        _ => AppColors.textSecondary,
      };

  static String statusLabel(String status) => switch (status) {
        BookingStatus.pending => 'Awaiting confirmation',
        BookingStatus.confirmed => 'Confirmed',
        BookingStatus.assigned => 'Provider assigned',
        BookingStatus.enRoute => 'Provider on the way',
        BookingStatus.pickedUp => 'Item picked up',
        BookingStatus.inProgress => 'In progress',
        BookingStatus.outForDelivery => 'On its way back',
        BookingStatus.completed => 'Completed',
        BookingStatus.cancelled => 'Cancelled',
        BookingStatus.disputed => 'Problem reported',
        BookingStatus.refunded => 'Refunded',
        _ => status,
      };

  Future<void> _confirmCancel(Booking booking) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Cancel this booking?'),
        content: Text(
          '${booking.serviceName}, ${friendlyDateTime(booking.scheduledAt)}, will be cancelled. '
          'This cannot be undone.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Keep booking')),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('Yes, cancel'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      setState(() => _cancelling = booking.id);
      context.read<BookingBloc>().add(CancelBookingRequested(booking.id));
    }
  }

  Future<void> _rate(Booking booking) async {
    final result = await showDialog<(int, String?)>(context: context, builder: (_) => const _RatingDialog());
    if (result == null || !mounted) return;
    final (stars, comment) = result;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await (widget.ratingApi ?? sl<RatingApi>()).rate(
        shopId: booking.shopId!,
        bookingId: booking.id,
        rating: stars.toDouble(),
        comment: comment,
      );
      if (mounted) setState(() => _rated[booking.id] = stars);
      messenger.showSnackBar(SnackBar(
        content: Text(comment == null ? 'Thanks for rating!' : 'Thanks for your review! It helps others choose.'),
        backgroundColor: AppColors.success,
      ));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    }
  }

  Future<void> _report(Booking booking) async {
    final report = await showDialog<(String, String)>(context: context, builder: (_) => const _ReportDialog());
    if (report == null || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    final bloc = context.read<BookingBloc>();
    try {
      await (widget.disputeApi ?? sl<DisputeApi>()).report(bookingId: booking.id, type: report.$1, description: report.$2);
      messenger.showSnackBar(const SnackBar(content: Text('Thanks. Our support team will look into it and get back to you.')));
      bloc.add(const RefreshBookings());
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    }
  }

  void _open(Widget page) => Navigator.push(context, MaterialPageRoute(builder: (_) => page)).then((_) {
        if (!mounted) return;
        context.read<BookingBloc>().add(const RefreshBookings());
        _loadPayments();
      });

  /// Pull-to-refresh: keeps the spinner up until the list has actually reloaded.
  Future<void> _refresh() async {
    final bloc = context.read<BookingBloc>();
    final done = bloc.stream.firstWhere((s) => s is BookingsLoaded || s is BookingError);
    bloc.add(const RefreshBookings());
    await Future.wait([done, _loadPayments()]);
  }

  Widget _card(Booking b) => _BookingCard(
        booking: b,
        statusColor: statusColor(b.status),
        statusLabel: statusLabel(b.status),
        cancelling: _cancelling == b.id,
        onCancel: b.canCancel && _cancelling != b.id ? () => _confirmCancel(b) : null,
        onTrack: b.canTrack ? () => _open(LiveTrackingPage(booking: b)) : null,
        onPay: b.canPay && _payments[b.id] != 'paid'
            ? () => _open(PaymentPage(
                  bookingId: b.id,
                  amount: b.totalAmount,
                  bookingNumber: b.bookingNumber,
                  serviceName: b.serviceName,
                  paymentApi: widget.paymentApi,
                ))
            : null,
        payment: _payments[b.id],
        ratedStars: _rated[b.id],
        onRate: b.canRate && !_rated.containsKey(b.id) ? () => _rate(b) : null,
        onReport: b.canDispute ? () => _report(b) : null,
        onDirections: b.canGetDirections ? () => showHowToGetThere(context, shopId: b.shopId!) : null,
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Bookings')),
      body: BlocConsumer<BookingBloc, BookingState>(
        listener: (context, state) {
          if (state is BookingCancelled) {
            setState(() => _cancelling = null);
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Booking cancelled'), backgroundColor: AppColors.success),
            );
          } else if (state is BookingActionFailed) {
            setState(() => _cancelling = null);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message), backgroundColor: AppColors.error),
            );
          }
        },
        // A cancel or refresh outcome is a message on top of the list, not a new screen.
        buildWhen: (previous, current) => current is! BookingCancelled && current is! BookingActionFailed,
        builder: (context, state) {
          if (state is BookingLoading || state is BookingInitial) {
            return const LoadingIndicator(message: 'Loading bookings...');
          }
          if (state is BookingError) {
            return AppErrorWidget(
              message: state.message,
              onRetry: () => context.read<BookingBloc>().add(const LoadUserBookings()),
            );
          }
          final bookings = state is BookingsLoaded ? state.bookings : const <Booking>[];
          if (bookings.isEmpty) {
            return RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                padding: const EdgeInsets.all(32),
                children: [
                  const SizedBox(height: 80),
                  const Icon(Icons.calendar_today_outlined, size: 64, color: AppColors.textDisabled),
                  const SizedBox(height: 16),
                  const Text('No bookings yet', style: AppTextStyles.subtitle1, textAlign: TextAlign.center),
                  const SizedBox(height: 4),
                  const Text(
                    'Book a salon visit, a doctor, a repair and more. Your bookings will show up here.',
                    style: AppTextStyles.body2,
                    textAlign: TextAlign.center,
                  ),
                  if (widget.onBrowseServices != null) ...[
                    const SizedBox(height: 24),
                    Center(
                      child: CustomButton(
                        label: 'Browse services',
                        width: 220,
                        leadingIcon: Icons.search,
                        onPressed: widget.onBrowseServices,
                      ),
                    ),
                  ],
                ],
              ),
            );
          }
          final (upcoming, past) = splitBookings(bookings);
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              children: [
                if (upcoming.isNotEmpty) ...[
                  _SectionHeader('Upcoming & active', count: upcoming.length),
                  for (final b in upcoming) Padding(padding: const EdgeInsets.only(bottom: 12), child: _card(b)),
                ],
                if (past.isNotEmpty) ...[
                  _SectionHeader('Past', count: past.length),
                  for (final b in past) Padding(padding: const EdgeInsets.only(bottom: 12), child: _card(b)),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

/// What a booking's status means to the customer, e.g. "Awaiting confirmation".
String bookingStatusLabel(String status) => _BookingHistoryPageState.statusLabel(status);

/// Bookings still ahead or under way (soonest first), and finished ones (latest first).
(List<Booking>, List<Booking>) splitBookings(List<Booking> bookings) {
  const finished = {BookingStatus.completed, BookingStatus.cancelled, BookingStatus.refunded};
  final upcoming = bookings.where((b) => !finished.contains(b.status)).toList()
    ..sort((a, b) => a.scheduledAt.compareTo(b.scheduledAt));
  final past = bookings.where((b) => finished.contains(b.status)).toList()
    ..sort((a, b) => b.scheduledAt.compareTo(a.scheduledAt));
  return (upcoming, past);
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final int count;

  const _SectionHeader(this.title, {required this.count});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 12, 4, 8),
        child: Semantics(
          header: true,
          child: Text('$title ($count)', style: AppTextStyles.subtitle2.copyWith(color: AppColors.textPrimary)),
        ),
      );
}

class _BookingCard extends StatelessWidget {
  final Booking booking;
  final Color statusColor;
  final String statusLabel;
  final VoidCallback? onCancel;
  final VoidCallback? onTrack;
  final VoidCallback? onPay;
  final VoidCallback? onRate;
  final VoidCallback? onReport;
  final VoidCallback? onDirections;
  final String? payment;
  final int? ratedStars;
  final bool cancelling;

  const _BookingCard({
    required this.booking,
    required this.statusColor,
    required this.statusLabel,
    this.onCancel,
    this.onTrack,
    this.onPay,
    this.onRate,
    this.onReport,
    this.onDirections,
    this.payment,
    this.ratedStars,
    this.cancelling = false,
  });

  Widget _detail(IconData icon, String text, {Color color = AppColors.textSecondary, int maxLines = 2}) => Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(padding: const EdgeInsets.only(top: 2), child: Icon(icon, size: 14, color: color)),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                text,
                style: AppTextStyles.caption.copyWith(color: color),
                maxLines: maxLines,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      );

  @override
  Widget build(BuildContext context) {
    final actions = <Widget>[
      if (onDirections != null)
        TextButton.icon(onPressed: onDirections, icon: const Icon(Icons.directions, size: 18), label: const Text('How to get there')),
      if (onTrack != null)
        TextButton.icon(onPressed: onTrack, icon: const Icon(Icons.location_on_outlined, size: 18), label: const Text('Track')),
      if (onPay != null)
        TextButton.icon(
          onPressed: onPay,
          icon: const Icon(Icons.payment, size: 18),
          label: Text(payment == 'cash' ? 'Pay online instead' : 'Pay ${rupees(booking.totalAmount)}'),
        ),
      if (onRate != null)
        TextButton.icon(onPressed: onRate, icon: const Icon(Icons.star_outline, size: 18), label: const Text('Rate')),
      if (onReport != null)
        TextButton.icon(onPressed: onReport, icon: const Icon(Icons.report_outlined, size: 18), label: const Text('Report a problem')),
      if (onCancel != null || cancelling)
        TextButton(
          onPressed: onCancel,
          style: TextButton.styleFrom(foregroundColor: AppColors.error),
          child: Text(cancelling ? 'Cancelling…' : 'Cancel booking'),
        ),
    ];
    final pickup = booking.serviceMode == 'PICKUP_DROP';
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: Text(booking.serviceName, style: AppTextStyles.subtitle1)),
                const SizedBox(width: 8),
                // Up to about half the card: a long status (or large text) wraps instead of pushing
                // the card wider than the screen.
                ConstrainedBox(
                  constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.45),
                  child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    statusLabel,
                    textAlign: TextAlign.center,
                    style: AppTextStyles.caption.copyWith(color: statusColor, fontWeight: FontWeight.w600),
                  ),
                ),
                ),
              ],
            ),
            if (booking.bookingNumber.isNotEmpty) Text('Booking #${booking.bookingNumber}', style: AppTextStyles.caption),
            const SizedBox(height: 4),
            _detail(Icons.calendar_today, friendlyDateTime(booking.scheduledAt)),
            if (booking.isOverdue(DateTime.now()))
              _detail(
                Icons.info_outline,
                booking.status == BookingStatus.pending
                    ? "This time has passed and the shop hasn't confirmed. You can cancel and book another time."
                    : 'This time has passed. If you missed it, contact the shop or cancel.',
                color: AppColors.warning,
                maxLines: 3,
              ),
            if (booking.serviceMode != 'AT_SHOP' || booking.itemDescription != null)
              _detail(
                pickup ? Icons.local_shipping_outlined : Icons.home_outlined,
                [
                  pickup ? 'Pickup & drop' : 'Home visit',
                  if (booking.itemDescription != null) booking.itemDescription!,
                ].join(' · '),
              ),
            if (booking.showsReadyBy)
              _detail(Icons.event_available, 'Expected back by ${friendlyDateTime(booking.readyBy!)}', color: AppColors.primary),
            if (booking.address.isNotEmpty) _detail(Icons.location_on, booking.address),
            const SizedBox(height: 8),
            Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 8,
              children: [
                Text(rupees(booking.totalAmount), style: AppTextStyles.subtitle1.copyWith(color: AppColors.primary)),
                if (payment != null)
                  Text(
                    payment == 'paid' ? 'Paid' : 'Paying in cash',
                    style: AppTextStyles.caption.copyWith(color: payment == 'paid' ? AppColors.success : AppColors.warning),
                  ),
                if (ratedStars != null)
                  Text('You rated it $ratedStars★', style: AppTextStyles.caption.copyWith(color: AppColors.success)),
              ],
            ),
            if (actions.isNotEmpty) ...[
              const Divider(height: 16),
              Wrap(alignment: WrapAlignment.end, spacing: 4, children: actions),
            ],
          ],
        ),
      ),
    );
  }
}

class _RatingDialog extends StatefulWidget {
  const _RatingDialog();

  @override
  State<_RatingDialog> createState() => _RatingDialogState();
}

/// Stars and an optional written review; pops with (stars, review or null).
class _RatingDialogState extends State<_RatingDialog> {
  int _stars = 5;
  final _review = TextEditingController();

  static const _words = ['Poor', 'Below average', 'Okay', 'Good', 'Excellent'];

  @override
  void dispose() {
    _review.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('How was it?'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            FittedBox(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(
                  5,
                  (i) => IconButton(
                    tooltip: '${i + 1} star${i == 0 ? '' : 's'}',
                    isSelected: i < _stars,
                    onPressed: () => setState(() => _stars = i + 1),
                    icon: Icon(i < _stars ? Icons.star : Icons.star_border, color: AppColors.starFilled, size: 32),
                  ),
                ),
              ),
            ),
            Text(_words[_stars - 1], style: AppTextStyles.subtitle2),
            const SizedBox(height: 12),
            TextField(
              controller: _review,
              maxLines: 4,
              minLines: 2,
              maxLength: 1000,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Write a review (optional)',
                hintText: 'What went well, what could be better?',
                helperText: 'Shown with your first name and last initial',
                helperMaxLines: 2,
                alignLabelWithHint: true,
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Not now')),
        TextButton(
          onPressed: () {
            final review = _review.text.trim();
            Navigator.pop(context, (_stars, review.isEmpty ? null : review));
          },
          child: const Text('Submit'),
        ),
      ],
    );
  }
}

/// Asks what went wrong; pops with (type, description).
class _ReportDialog extends StatefulWidget {
  const _ReportDialog();

  @override
  State<_ReportDialog> createState() => _ReportDialogState();
}

class _ReportDialogState extends State<_ReportDialog> {
  String _type = disputeTypes.keys.first;
  final _description = TextEditingController();

  @override
  void dispose() {
    _description.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final valid = _description.text.trim().length >= 3;
    return AlertDialog(
      title: const Text('Report a problem'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DropdownButtonFormField<String>(
              initialValue: _type,
              isExpanded: true,
              items: [
                for (final e in disputeTypes.entries) DropdownMenuItem(value: e.key, child: Text(e.value)),
              ],
              onChanged: (v) => setState(() => _type = v ?? _type),
              decoration: const InputDecoration(labelText: 'What went wrong?'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _description,
              maxLines: 4,
              maxLength: 2000,
              textCapitalization: TextCapitalization.sentences,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                labelText: 'Tell us what happened',
                helperText: 'At least 3 characters',
                alignLabelWithHint: true,
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        TextButton(
          onPressed: valid ? () => Navigator.pop(context, (_type, _description.text.trim())) : null,
          child: const Text('Send'),
        ),
      ],
    );
  }
}
