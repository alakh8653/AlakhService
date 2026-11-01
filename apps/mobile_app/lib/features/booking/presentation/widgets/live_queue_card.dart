import 'dart:async';

import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/utils/format.dart';
import '../../data/booking_queue_api.dart';

/// Today's queue for a booking at the shop: place in line, people ahead, expected wait and the range of the
/// start, who will serve them, and whether the shop is running late; with "I'm here" to check in.
/// Refreshes itself; shows nothing when the booking has no live queue.
class LiveQueueCard extends StatefulWidget {
  final String bookingId;
  final BookingQueueApi? api;
  final Duration refreshEvery;

  const LiveQueueCard({super.key, required this.bookingId, this.api, this.refreshEvery = const Duration(seconds: 30)});

  @override
  State<LiveQueueCard> createState() => _LiveQueueCardState();
}

class _LiveQueueCardState extends State<LiveQueueCard> {
  late final BookingQueueApi? _api = widget.api ?? (sl.isRegistered<BookingQueueApi>() ? sl<BookingQueueApi>() : null);
  BookingQueue? _queue;
  Timer? _timer;
  bool _checkingIn = false;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(widget.refreshEvery, (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    final api = _api;
    if (api == null) return;
    try {
      final queue = await api.forBooking(widget.bookingId);
      if (!mounted) return;
      setState(() => _queue = queue);
      if (!queue.isLive) _timer?.cancel(); // nothing will change today
    } catch (_) {
      // Shown again on the next refresh; the booking's own details stay on screen.
    }
  }

  Future<void> _checkIn() async {
    final api = _api;
    if (api == null || _checkingIn) return;
    setState(() => _checkingIn = true);
    try {
      final queue = await api.checkIn(widget.bookingId);
      if (mounted) setState(() => _queue = queue);
    } catch (_) {
      // The button stays; the next refresh shows where they stand.
    } finally {
      if (mounted) setState(() => _checkingIn = false);
    }
  }

  String _expected(BookingQueue queue) {
    final l10n = context.l10n;
    final from = queue.etaMin, to = queue.etaMax;
    if (from != null && to != null && to.difference(from).inMinutes >= 2) {
      return l10n.liveQueueBetween(clockTime(from), clockTime(to));
    }
    return l10n.queueExpectedAround(clockTime(queue.estimatedStart!));
  }

  @override
  Widget build(BuildContext context) {
    final queue = _queue;
    if (queue == null || !queue.isLive) return const SizedBox.shrink();
    final l10n = context.l10n;
    final late = queue.runningLateMinutes ?? 0;
    final Widget body = switch (queue.state) {
      'IN_PROGRESS' => Text(l10n.liveQueueInProgress, style: AppTextStyles.subtitle1.copyWith(color: context.palette.success)),
      'CHECK_IN_NEEDED' => Text(l10n.liveQueueCheckInNeeded, style: AppTextStyles.subtitle1.copyWith(color: context.colors.error)),
      'UNSERVABLE' => Text(l10n.liveQueueUnservable, style: AppTextStyles.subtitle1.copyWith(color: context.colors.error)),
      'YOUR_TURN' => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.queueYourTurn, style: AppTextStyles.heading3.copyWith(color: context.palette.success)),
            Text(l10n.liveQueueGoIn, style: AppTextStyles.body2.themed(context)),
          ],
        ),
      _ => Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 64,
              height: 64,
              alignment: Alignment.center,
              decoration: BoxDecoration(shape: BoxShape.circle, color: context.colors.primaryContainer),
              child: Text(
                '#${queue.position}',
                semanticsLabel: l10n.queuePositionSemantics(queue.position ?? 0),
                style: AppTextStyles.heading3.copyWith(color: context.colors.primary),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    (queue.waitMinutes ?? 0) > 0 ? l10n.liveQueueWait(l10n.queueWaitMinutes(queue.waitMinutes!)) : l10n.queueYoureNext,
                    style: AppTextStyles.subtitle1,
                  ),
                  if (queue.estimatedStart != null) Text(_expected(queue), style: AppTextStyles.body2.themed(context)),
                  if (queue.staffName != null) Text(l10n.liveQueueWith(queue.staffName!), style: AppTextStyles.body2.themed(context)),
                  Text(l10n.queueAhead(queue.peopleAhead ?? 0), style: AppTextStyles.body2.themed(context)),
                  if ((queue.beingServed ?? 0) > 0)
                    Text(l10n.liveQueueBeingServed(queue.beingServed!), style: AppTextStyles.caption.themed(context)),
                ],
              ),
            ),
          ],
        ),
    };
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.people_alt_outlined, size: 18, color: context.colors.primary),
                const SizedBox(width: 6),
                Text(l10n.liveQueueTitle, style: AppTextStyles.subtitle2.copyWith(color: context.colors.primary)),
              ],
            ),
            const SizedBox(height: 12),
            body,
            if (queue.reason == 'PREFERRED_UNAVAILABLE') ...[
              const SizedBox(height: 8),
              Text(l10n.liveQueueStaffAway, style: AppTextStyles.caption.themed(context)),
            ],
            if (late > 0 && const {'WAITING', 'YOUR_TURN'}.contains(queue.state)) ...[
              const SizedBox(height: 8),
              Text(l10n.liveQueueRunningLate(late), style: AppTextStyles.caption.copyWith(color: context.colors.error)),
            ],
            if (queue.state == 'WAITING') ...[
              const SizedBox(height: 8),
              Text(l10n.queueWeWillNotify, style: AppTextStyles.caption.themed(context)),
            ],
            if (queue.canCheckIn) ...[
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: _checkingIn ? null : _checkIn,
                icon: const Icon(Icons.how_to_reg_outlined),
                label: Text(l10n.liveQueueCheckIn),
              ),
            ] else if (queue.checkedIn && queue.state != 'IN_PROGRESS') ...[
              const SizedBox(height: 8),
              Text(l10n.liveQueueCheckedIn, style: AppTextStyles.caption.copyWith(color: context.palette.success)),
            ],
          ],
        ),
      ),
    );
  }
}
