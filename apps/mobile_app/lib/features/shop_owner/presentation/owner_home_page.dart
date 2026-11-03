import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../features/auth/domain/entities/user.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../../booking/presentation/pages/booking_history_page.dart';
import '../../chat/presentation/booking_chat_page.dart';
import '../../shop_line/data/shop_line_api.dart';
import '../../shop_line/presentation/shop_line_page.dart';
import '../data/shop_owner_api.dart';
import 'owner_reports_page.dart';
import 'owner_settings_pages.dart';
import 'verification_page.dart';

/// The owner's home on the phone: new requests with big Accept and Decline buttons, then the work ahead,
/// then everything else about the business. Refreshes itself, so a request shows up without push.
class OwnerHomePage extends StatefulWidget {
  final OwnedShop shop;
  final User user;
  final ShopOwnerApi? api;
  final ShopLineApi? lineApi;
  final Duration refreshEvery;

  /// Moves to the side of the app for booking services.
  final VoidCallback? onSwitchToBooking;

  const OwnerHomePage({
    super.key,
    required this.shop,
    required this.user,
    this.api,
    this.lineApi,
    this.refreshEvery = const Duration(seconds: 30),
    this.onSwitchToBooking,
  });

  @override
  State<OwnerHomePage> createState() => _OwnerHomePageState();
}

class _OwnerHomePageState extends State<OwnerHomePage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  OwnerShop? _shop;
  List<OwnerBooking>? _bookings;
  Map<String, String> _serviceNames = const {};
  String? _error;
  String? _busy;
  Timer? _timer;

  String get _shopId => widget.shop.id;

  static const _finished = {'COMPLETED', 'CANCELLED', 'REFUNDED', 'DISPUTED'};

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(widget.refreshEvery, (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final shop = await _api.shop(_shopId);
      final bookings = await _api.bookings(_shopId);
      final services = await _api.services(_shopId);
      if (!mounted) return;
      setState(() {
        _shop = shop;
        _bookings = bookings;
        _serviceNames = {for (final s in services) s.id: s.name};
        _error = null;
      });
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<String?> _askReason(OwnerAction action) => showDialog<String>(
        context: context,
        builder: (_) => _ReasonDialog(declining: action == OwnerAction.decline),
      );

  Future<void> _do(OwnerBooking booking, OwnerAction action) async {
    String? reason;
    if (action == OwnerAction.decline || action == OwnerAction.cancel) {
      reason = await _askReason(action);
      if (reason == null || !mounted) return;
    }
    setState(() => _busy = booking.id);
    try {
      if (reason != null) {
        await _api.cancel(booking.id, reason);
      } else if (action == OwnerAction.goMyself) {
        await _api.assignToMe(booking.id, _shopId, widget.user.id, widget.user.name);
      } else {
        await _api.setStatus(booking.id, ownerActionTargets[action]!);
      }
      await _load();
    } on ServerException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  String _actionLabel(OwnerAction action, AppLocalizations l10n) => switch (action) {
        OwnerAction.accept => l10n.ownerAccept,
        OwnerAction.decline => l10n.ownerDecline,
        OwnerAction.customerArrived => l10n.ownerCustomerArrived,
        OwnerAction.goMyself => l10n.ownerGoMyself,
        OwnerAction.onTheWay => l10n.ownerOnTheWay,
        OwnerAction.onTheWayToCollect => l10n.ownerOnTheWayToCollect,
        OwnerAction.pickedUp => l10n.ownerPickedUp,
        OwnerAction.startWork => l10n.ownerStartWork,
        OwnerAction.start => l10n.ownerStartService,
        OwnerAction.sendBack => l10n.ownerSendBack,
        OwnerAction.delivered => l10n.ownerDelivered,
        OwnerAction.complete => l10n.ownerComplete,
        OwnerAction.cancel => l10n.ownerCancelBooking,
      };

  String _paymentLabel(String status, AppLocalizations l10n) => switch (status) {
        'PAID' => l10n.ownerPaid,
        'REFUNDED' => l10n.ownerRefunded,
        'PARTIALLY_REFUNDED' => l10n.ownerPartlyRefunded,
        _ => l10n.ownerNotPaid,
      };

  Future<void> _open(Widget page) async {
    await Navigator.push<void>(context, MaterialPageRoute(builder: (_) => page));
    if (mounted) await _load();
  }

  Widget _banner(OwnerShop shop, AppLocalizations l10n) {
    if (shop.approved) return const SizedBox.shrink();
    final (Color color, String text) = shop.rejected
        ? (AppColors.error, l10n.ownerStatusRejected(shop.rejectionReason ?? ''))
        : shop.waitingForReview
            ? (AppColors.warning, l10n.ownerStatusInReview)
            : (AppColors.primary, l10n.ownerBannerFinish);
    return Card(
      key: const ValueKey('owner-banner'),
      margin: const EdgeInsets.only(bottom: 16),
      color: color.withValues(alpha: 0.1),
      child: ListTile(
        leading: Icon(Icons.verified_user_outlined, color: color),
        title: Text(text, style: AppTextStyles.body2.themed(context)),
        trailing: shop.waitingForReview ? null : const Icon(Icons.chevron_right),
        onTap: shop.waitingForReview ? null : () => _open(VerificationPage(shopId: _shopId, api: widget.api)),
      ),
    );
  }

  Widget _bookingCard(OwnerBooking booking, AppLocalizations l10n) {
    final actions = ownerActions(booking.status, booking.mode);
    final busy = _busy == booking.id;
    final main = actions.isEmpty ? null : actions.first;
    final others = actions.skip(1).toList();
    final isRequest = booking.status == 'PENDING';
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(child: Text(booking.customerName, style: AppTextStyles.heading3)),
                Text(rupees(booking.totalCents / 100), style: AppTextStyles.body1),
              ],
            ),
            const SizedBox(height: 4),
            Text(_serviceNames[booking.serviceId] ?? l10n.ownerAService, style: AppTextStyles.body1),
            const SizedBox(height: 4),
            Text(
              '${isRequest ? l10n.ownerNeedsYourAnswer : bookingStatusLabel(l10n, booking.status)} · ${_paymentLabel(booking.paymentStatus, l10n)}',
              style: AppTextStyles.subtitle2.copyWith(color: isRequest ? AppColors.warning : AppColors.primary),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(Icons.schedule, size: 16, color: context.palette.muted),
                const SizedBox(width: 4),
                Expanded(child: Text(friendlyDateTime(booking.scheduledAt, l10n: l10n), style: AppTextStyles.body2.themed(context))),
              ],
            ),
            if (booking.mode != modeAtShop) ...[
              const SizedBox(height: 4),
              Row(
                children: [
                  Icon(Icons.home_outlined, size: 16, color: context.palette.muted),
                  const SizedBox(width: 4),
                  Text(booking.mode == modeAtHome ? l10n.ownerHomeVisit : l10n.ownerPickupDrop, style: AppTextStyles.body2.themed(context)),
                ],
              ),
            ],
            if ((booking.notes ?? '').isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(booking.notes!, style: AppTextStyles.caption.themed(context)),
            ],
            const SizedBox(height: 12),
            if (busy)
              const Center(child: Padding(padding: EdgeInsets.all(8), child: CircularProgressIndicator()))
            else if (isRequest)
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.error,
                        minimumSize: const Size.fromHeight(52),
                      ),
                      onPressed: () => _do(booking, OwnerAction.decline),
                      child: Text(l10n.ownerDecline),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                      onPressed: () => _do(booking, OwnerAction.accept),
                      child: Text(l10n.ownerAccept),
                    ),
                  ),
                ],
              )
            else ...[
              if (main != null)
                FilledButton(
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                  onPressed: () => _do(booking, main),
                  child: Text(_actionLabel(main, l10n)),
                ),
              Wrap(
                alignment: WrapAlignment.end,
                children: [
                  TextButton.icon(
                    icon: const Icon(Icons.chat_bubble_outline, size: 18),
                    label: Text(l10n.ownerMessage),
                    onPressed: () => _open(BookingChatPage(bookingId: booking.id, subtitle: booking.customerName)),
                  ),
                  for (final action in others)
                    TextButton(
                      style: action == OwnerAction.cancel ? TextButton.styleFrom(foregroundColor: AppColors.error) : null,
                      onPressed: () => _do(booking, action),
                      child: Text(_actionLabel(action, l10n)),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _link(IconData icon, String label, Widget Function() page) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(icon, color: context.palette.muted),
        title: Text(label, style: AppTextStyles.body1),
        trailing: Icon(Icons.chevron_right, color: context.palette.muted),
        onTap: () => _open(page()),
      );

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final bookings = _bookings;
    final shop = _shop;
    if (bookings == null || shop == null) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.shop.name)),
        body: _error == null
            ? const LoadingIndicator()
            : Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Padding(padding: const EdgeInsets.all(24), child: Text(_error!, textAlign: TextAlign.center)),
                    TextButton(onPressed: _load, child: Text(l10n.retry)),
                  ],
                ),
              ),
      );
    }
    final requests = bookings.where((b) => b.status == 'PENDING').toList();
    final ahead = bookings.where((b) => b.status != 'PENDING' && !_finished.contains(b.status)).toList();
    return Scaffold(
      appBar: AppBar(
        title: Text(shop.name),
        actions: [
          if (widget.onSwitchToBooking != null)
            IconButton(
              key: const ValueKey('switch-to-booking'),
              icon: const Icon(Icons.swap_horiz),
              tooltip: l10n.modeSwitchToBooking,
              onPressed: widget.onSwitchToBooking,
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _banner(shop, l10n),
            Text(l10n.ownerNewRequests(requests.length), style: AppTextStyles.heading3),
            const SizedBox(height: 8),
            if (requests.isEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(l10n.ownerNoRequests, style: AppTextStyles.body2.themed(context)),
              ),
            for (final booking in requests) _bookingCard(booking, l10n),
            const SizedBox(height: 8),
            Text(l10n.ownerComingUp, style: AppTextStyles.heading3),
            const SizedBox(height: 8),
            if (ahead.isEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(l10n.ownerNothingAhead, style: AppTextStyles.body2.themed(context)),
              ),
            for (final booking in ahead) _bookingCard(booking, l10n),
            const SizedBox(height: 8),
            Text(l10n.ownerManage, style: AppTextStyles.heading3),
            _link(
              Icons.groups_outlined,
              l10n.ownerLiveLine,
              () => ShopLinePage(shop: widget.shop, api: widget.lineApi),
            ),
            _link(Icons.bar_chart, l10n.ownerReports, () => OwnerReportsPage(shopId: _shopId, api: widget.api)),
            _link(Icons.content_cut, l10n.ownerMyServices, () => OwnerServicesPage(shopId: _shopId, api: widget.api)),
            _link(Icons.schedule, l10n.ownerOpeningHours, () => OwnerHoursPage(shopId: _shopId, api: widget.api)),
            _link(
              Icons.verified_user_outlined,
              l10n.ownerVerificationTitle,
              () => VerificationPage(shopId: _shopId, api: widget.api),
            ),
          ],
        ),
      ),
    );
  }
}

/// Asks why a booking is being turned down, and pops with the reason. Keeps its own text controller, which
/// has to outlive the dialog's closing animation.
class _ReasonDialog extends StatefulWidget {
  final bool declining;

  const _ReasonDialog({required this.declining});

  @override
  State<_ReasonDialog> createState() => _ReasonDialogState();
}

class _ReasonDialogState extends State<_ReasonDialog> {
  final _reason = TextEditingController();

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return AlertDialog(
      title: Text(widget.declining ? l10n.ownerDeclineTitle : l10n.ownerCancelTitle),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.ownerRefundNote),
          const SizedBox(height: 12),
          TextField(
            controller: _reason,
            autofocus: true,
            decoration: InputDecoration(labelText: l10n.ownerReasonLabel),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(l10n.notNow)),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: AppColors.error),
          onPressed: () {
            final reason = _reason.text.trim();
            Navigator.pop(context, reason.isEmpty ? l10n.ownerDefaultReason : reason);
          },
          child: Text(widget.declining ? l10n.ownerDecline : l10n.ownerCancelBooking),
        ),
      ],
    );
  }
}
