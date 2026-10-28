import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/utils/format.dart';
import '../../data/availability_api.dart';
import '../../domain/entities/booking.dart';
import '../../domain/repositories/booking_repository.dart';
import 'booking_page.dart' show BookingSlots, DayChip;

/// Moves a booking to another free time of the same service. Pops with the updated booking.
///
/// The times come from booking_service as when booking, with the booking's own place counted as free;
/// booking_service checks the new time again, and how often and how late the customer may move it.
class ReschedulePage extends StatefulWidget {
  final Booking booking;
  final BookingRepository? repository;
  final AvailabilityApi? availabilityApi;

  /// The current time (replaceable in tests).
  final DateTime Function() clock;

  const ReschedulePage({super.key, required this.booking, this.repository, this.availabilityApi, this.clock = DateTime.now});

  @override
  State<ReschedulePage> createState() => _ReschedulePageState();
}

class _ReschedulePageState extends State<ReschedulePage> {
  late final AvailabilityApi _availabilityApi = widget.availabilityApi ?? sl<AvailabilityApi>();
  BookingRepository get _repository => widget.repository ?? sl<BookingRepository>();
  late final List<DateTime> _days = BookingSlots.upcomingDays(now: widget.clock());
  late DateTime _day = _days.first;
  final Map<DateTime, DayAvailability> _availability = {};
  final Set<DateTime> _failed = {};
  // The chosen start: the instant to send, and the shop's wall-clock time to show.
  DateTime? _at, _shown;
  bool _saving = false;

  Booking get booking => widget.booking;

  @override
  void initState() {
    super.initState();
    _load(_day);
  }

  Future<void> _load(DateTime day, {bool refresh = false}) async {
    if (!refresh && _availability.containsKey(day)) return;
    setState(() => _failed.remove(day));
    try {
      final times = await _availabilityApi.forDay(booking.serviceId, day, movingBookingId: booking.id);
      if (mounted) setState(() => _availability[day] = times);
    } catch (_) {
      if (mounted) setState(() => _failed.add(day));
    }
  }

  /// (shown, at) for each time on offer on [day], without the booking's current time; null until known.
  List<(DateTime, DateTime)>? _slots(DateTime day) {
    final times = _availability[day];
    if (times == null) return null;
    final all = times.hoursConfigured
        ? [for (final s in times.slots) (DateTime(day.year, day.month, day.day, s.hour, s.minute), s.at)]
        : [for (final t in BookingSlots.on(day, now: widget.clock())) (t, t)];
    final current = booking.scheduledAt.toUtc();
    return all.where((s) => s.$2.toUtc() != current).toList();
  }

  void _chooseDay(DateTime day) {
    setState(() {
      _day = day;
      _at = _shown = null;
    });
    _load(day);
  }

  Future<void> _confirm() async {
    final at = _at;
    if (at == null || _saving) return;
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final l10n = context.l10n;
    setState(() => _saving = true);
    final result = await _repository.rescheduleBooking(booking.id, at);
    if (!mounted) return;
    setState(() => _saving = false);
    result.fold(
      (failure) {
        // The time may just have been taken: show what is free now.
        _load(_day, refresh: true);
        setState(() => _at = _shown = null);
        messenger.showSnackBar(SnackBar(content: Text(failure.message), backgroundColor: AppColors.error));
      },
      (moved) {
        messenger.showSnackBar(SnackBar(
          content: Text(l10n.bookingRescheduled(friendlyDateTime(moved.scheduledAt, l10n: l10n))),
          backgroundColor: AppColors.success,
        ));
        navigator.pop(moved);
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final slots = _slots(_day);
    final left = Booking.maxReschedules - booking.rescheduleCount;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.rescheduleTitle)),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
          child: FilledButton(
            onPressed: _at == null || _saving ? null : _confirm,
            child: Text(_saving ? l10n.rescheduling : l10n.rescheduleConfirm),
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(booking.serviceName, style: AppTextStyles.heading3),
          const SizedBox(height: 4),
          Text(l10n.rescheduleCurrent(friendlyDateTime(booking.scheduledAt, l10n: l10n)), style: AppTextStyles.body2.themed(context)),
          const SizedBox(height: 8),
          Text(l10n.rescheduleRule(left < 0 ? 0 : left), style: AppTextStyles.caption.copyWith(color: context.palette.muted)),
          const SizedBox(height: 20),
          SizedBox(
            height: 64,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: _days.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (context, i) =>
                  DayChip(day: _days[i], now: widget.clock(), selected: _days[i] == _day, onTap: () => _chooseDay(_days[i])),
            ),
          ),
          const SizedBox(height: 16),
          if (slots == null && _failed.contains(_day))
            Row(
              children: [
                Expanded(child: Text(l10n.timesLoadFailed, style: AppTextStyles.body2.themed(context))),
                TextButton(onPressed: () => _load(_day, refresh: true), child: Text(l10n.retry)),
              ],
            )
          else if (slots == null)
            const Center(child: Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator()))
          else if (slots.isEmpty)
            Text(
              _availability[_day]?.message ?? l10n.noTimesOnDay,
              style: AppTextStyles.body2.themed(context),
            )
          else
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (shown, at) in slots)
                  ChoiceChip(
                    label: Text(clockTime(shown)),
                    showCheckmark: false,
                    selected: _at == at,
                    onSelected: (_) => setState(() {
                      _at = at;
                      _shown = shown;
                    }),
                  ),
              ],
            ),
          if (_shown != null) ...[
            const SizedBox(height: 16),
            Text(friendlyDateTime(_shown!, l10n: l10n), style: AppTextStyles.subtitle2.copyWith(color: context.colors.primary)),
          ],
        ],
      ),
    );
  }
}
