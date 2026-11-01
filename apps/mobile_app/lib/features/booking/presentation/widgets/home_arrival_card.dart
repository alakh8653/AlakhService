import 'dart:async';

import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/utils/format.dart';
import '../../data/home_arrival_api.dart';

/// A home visit today: when the professional will arrive (with a range), how many visits are before this
/// one on their route, whether they are on the way or here. Refreshes itself; shows nothing otherwise.
class HomeArrivalCard extends StatefulWidget {
  final String bookingId;
  final HomeArrivalApi? api;
  final Duration refreshEvery;

  const HomeArrivalCard({super.key, required this.bookingId, this.api, this.refreshEvery = const Duration(seconds: 60)});

  @override
  State<HomeArrivalCard> createState() => _HomeArrivalCardState();
}

class _HomeArrivalCardState extends State<HomeArrivalCard> {
  late final HomeArrivalApi? _api = widget.api ?? (sl.isRegistered<HomeArrivalApi>() ? sl<HomeArrivalApi>() : null);
  HomeArrival? _arrival;
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
      final arrival = await api.forBooking(widget.bookingId);
      if (!mounted) return;
      setState(() => _arrival = arrival);
      if (!arrival.isLive || arrival.state == 'ARRIVED') _timer?.cancel();
    } catch (_) {
      // Shown again on the next refresh.
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = _arrival;
    if (a == null || !a.isLive) return const SizedBox.shrink();
    final l10n = context.l10n;
    final at = a.arriveAt;
    final from = a.arriveMin, to = a.arriveMax;
    final ranged = from != null && to != null && to.difference(from).inMinutes >= 2;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.home_work_outlined, size: 18, color: context.colors.primary),
              const SizedBox(width: 6),
              Text(l10n.homeArrivalTitle, style: AppTextStyles.subtitle2.copyWith(color: context.colors.primary)),
            ]),
            const SizedBox(height: 12),
            if (a.state == 'ARRIVED')
              Text(l10n.homeArrivalHere, style: AppTextStyles.subtitle1.copyWith(color: context.palette.success))
            else if (at != null) ...[
              Text(
                a.state == 'ON_THE_WAY' ? l10n.homeArrivalOnTheWay(clockTime(at)) : l10n.homeArrivalAround(clockTime(at)),
                style: AppTextStyles.subtitle1,
              ),
              if (ranged) Text(l10n.homeArrivalBetween(clockTime(from), clockTime(to)), style: AppTextStyles.body2.themed(context)),
              if (a.state == 'PLANNED' && a.jobsBefore != null)
                Text(l10n.homeArrivalBefore(a.jobsBefore!), style: AppTextStyles.body2.themed(context)),
              if (a.lateMinutes > 0) ...[
                const SizedBox(height: 8),
                Text(l10n.homeArrivalLate(a.lateMinutes), style: AppTextStyles.caption.copyWith(color: context.colors.error)),
              ],
            ],
          ],
        ),
      ),
    );
  }
}
