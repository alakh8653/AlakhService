import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_text_styles.dart';
import '../l10n/l10n.dart';

/// Whether the device has a network: the current state first, then each change. One entry per active
/// interface (wifi, mobile, ...); [ConnectivityResult.none] alone means offline.
Stream<bool> onlineStatus(Connectivity connectivity) async* {
  bool online(List<ConnectivityResult> results) => results.any((r) => r != ConnectivityResult.none);
  yield online(await connectivity.checkConnectivity());
  yield* connectivity.onConnectivityChanged.map(online);
}

/// Wraps every screen (from MaterialApp.builder) with a slim strip at the top while the device is
/// offline, and a brief "Back online" once it reconnects. [online] is replaceable in tests.
class OfflineBanner extends StatefulWidget {
  final Stream<bool> online;
  final Widget child;

  /// How long "Back online" stays up.
  final Duration backOnlineFor;

  const OfflineBanner({
    super.key,
    required this.online,
    required this.child,
    this.backOnlineFor = const Duration(seconds: 3),
  });

  @override
  State<OfflineBanner> createState() => _OfflineBannerState();
}

enum _Shown { nothing, offline, backOnline }

class _OfflineBannerState extends State<OfflineBanner> {
  StreamSubscription<bool>? _subscription;
  Timer? _hide;
  _Shown _shown = _Shown.nothing;

  @override
  void initState() {
    super.initState();
    _listen();
  }

  @override
  void didUpdateWidget(OfflineBanner oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.online != widget.online) _listen();
  }

  void _listen() {
    _subscription?.cancel();
    // A device that can't report its network (no plugin) is taken as online: no strip.
    _subscription = widget.online.distinct().listen(_onChange, onError: (Object _) {});
  }

  void _onChange(bool online) {
    _hide?.cancel();
    if (!online) return setState(() => _shown = _Shown.offline);
    // Coming back is worth a word; being online from the start is not.
    if (_shown != _Shown.offline) return;
    setState(() => _shown = _Shown.backOnline);
    _hide = Timer(widget.backOnlineFor, () {
      if (mounted) setState(() => _shown = _Shown.nothing);
    });
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _hide?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final showing = _shown != _Shown.nothing;
    // The same two children every time, so the screens below keep their state as the strip comes and
    // goes. The strip sits above the screens' own app bars and takes over the status-bar inset.
    return Column(
      children: [
        if (showing) _strip(context) else const SizedBox.shrink(),
        Expanded(child: MediaQuery.removePadding(context: context, removeTop: showing, child: widget.child)),
      ],
    );
  }

  Widget _strip(BuildContext context) {
    final offline = _shown == _Shown.offline;
    final l10n = context.l10n;
    return Semantics(
      liveRegion: true,
      container: true,
      child: Material(
        color: offline ? AppColors.textPrimary : AppColors.success,
        child: Padding(
          padding: EdgeInsets.fromLTRB(16, MediaQuery.paddingOf(context).top + 6, 16, 6),
          child: Row(
            children: [
              Icon(offline ? Icons.cloud_off : Icons.cloud_done_outlined, size: 16, color: AppColors.textLight),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  offline ? l10n.offlineBanner : l10n.backOnline,
                  style: AppTextStyles.caption.copyWith(color: AppColors.textLight),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
