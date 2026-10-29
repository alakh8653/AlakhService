import 'dart:async';

import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/utils/format.dart';
import '../../data/booking_queue_api.dart';

/// Today's queue for a booking at the shop: place in line, people ahead, expected wait and start, and
/// whether the shop is running late. Refreshes itself; shows nothing when the booking has no live queue.
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

  @override
  Widget build(BuildContext context) {
    final queue = _queue;
    if (queue == null || !queue.isLive) return const SizedBox.shrink();
    final l10n = context.l10n;
    final late = queue.runningLateMinutes ?? 0;
    final Widget body = switch (queue.state) {
      'IN_PROGRESS' => Text(l10n.liveQueueInProgress, style: AppTextStyles.subtitle1.copyWith(color: context.palette.success)),
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
                  if (queue.estimatedStart != null)
                    Text(l10n.queueExpectedAround(clockTime(queue.estimatedStart!)), style: AppTextStyles.body2.themed(context)),
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
            if (late > 0 && queue.state != 'IN_PROGRESS') ...[
              const SizedBox(height: 8),
              Text(l10n.liveQueueRunningLate(late), style: AppTextStyles.caption.copyWith(color: context.colors.error)),
            ],
            if (queue.state == 'WAITING') ...[
              const SizedBox(height: 8),
              Text(l10n.queueWeWillNotify, style: AppTextStyles.caption.themed(context)),
            ],
          ],
        ),
      ),
    );
  }
}
