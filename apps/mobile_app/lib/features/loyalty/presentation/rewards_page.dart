import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/network/api_errors.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/error_widget.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../data/loyalty_api.dart';

/// The customer's points (earned on bookings, spent on new ones), their code to invite friends, and a
/// place to enter the code of the friend who invited them.
class RewardsPage extends StatefulWidget {
  final LoyaltyApi? api;

  /// Opens a share link (WhatsApp); replaceable in tests.
  final Future<bool> Function(Uri)? openLink;

  const RewardsPage({super.key, this.api, this.openLink});

  @override
  State<RewardsPage> createState() => _RewardsPageState();
}

class _RewardsPageState extends State<RewardsPage> {
  late final LoyaltyApi _api = widget.api ?? sl<LoyaltyApi>();
  final _code = TextEditingController();
  LoyaltySummary? _summary;
  String? _error;
  bool _sendingCode = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final summary = await _api.summary();
      if (mounted) setState(() => _summary = summary);
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  Future<void> _useCode() async {
    final code = _code.text.trim();
    if (code.isEmpty || _sendingCode) return;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _sendingCode = true);
    try {
      final message = await _api.useReferralCode(code);
      messenger.showSnackBar(SnackBar(content: Text(message), backgroundColor: AppColors.success));
      _code.clear();
      await _load();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    } finally {
      if (mounted) setState(() => _sendingCode = false);
    }
  }

  Future<void> _copy(String code) async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = context.l10n;
    await Clipboard.setData(ClipboardData(text: code));
    messenger.showSnackBar(SnackBar(content: Text(l10n.referralCopied)));
  }

  Future<void> _share(LoyaltySummary s) async {
    final text = context.l10n.referralShareText(s.referralCode, '${s.referralBonusPoints}');
    final open = widget.openLink ?? ((uri) => launchUrl(uri, mode: LaunchMode.externalApplication));
    await open(Uri.parse('https://wa.me/?text=${Uri.encodeComponent(text)}'));
  }

  String _entryLabel(PointsEntry e) {
    final l10n = context.l10n;
    return switch (e.kind) {
      'EARN' => l10n.pointsEarned,
      'REDEEM' => l10n.pointsSpent,
      'REDEEM_RETURN' => l10n.pointsReturned,
      'REFERRAL_BONUS' => l10n.pointsReferral,
      'CLAWBACK' => l10n.pointsTakenBack,
      _ => e.note ?? e.kind,
    };
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final s = _summary;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.rewardsTitle)),
      body: s == null
          ? (_error != null ? AppErrorWidget(message: _error!, onRetry: _load) : const LoadingIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Card(
                    color: context.colors.primaryContainer,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(l10n.pointsBalance(s.points), style: AppTextStyles.heading2.copyWith(color: context.colors.onPrimaryContainer)),
                          Text(l10n.pointsWorth(rupees(s.valueCents / 100)), style: AppTextStyles.body2.copyWith(color: context.colors.onPrimaryContainer)),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    l10n.pointsRules('${s.pointsPer100Rupees}', '${s.redeemMaxPercent}'),
                    style: AppTextStyles.caption.copyWith(color: context.palette.muted),
                  ),
                  const SizedBox(height: 24),
                  Text(l10n.referralTitle, style: AppTextStyles.subtitle1),
                  const SizedBox(height: 4),
                  Text(l10n.referralBody('${s.referralBonusPoints}'), style: AppTextStyles.body2.themed(context)),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: SelectableText(s.referralCode, style: AppTextStyles.heading3.copyWith(letterSpacing: 2)),
                      ),
                      IconButton(tooltip: l10n.referralCopy, icon: const Icon(Icons.copy), onPressed: () => _copy(s.referralCode)),
                      IconButton(tooltip: l10n.referralShare, icon: const Icon(Icons.share), onPressed: () => _share(s)),
                    ],
                  ),
                  if (s.friendsRewarded + s.friendsPending > 0)
                    Text(l10n.referralFriends(s.friendsRewarded, s.friendsPending), style: AppTextStyles.caption.themed(context)),
                  if (!s.referredByFriend) ...[
                    const SizedBox(height: 24),
                    Text(l10n.referralEnterTitle, style: AppTextStyles.subtitle1),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _code,
                            textCapitalization: TextCapitalization.characters,
                            decoration: InputDecoration(labelText: l10n.referralCodeLabel),
                            onSubmitted: (_) => _useCode(),
                          ),
                        ),
                        const SizedBox(width: 8),
                        TextButton(onPressed: _sendingCode ? null : _useCode, child: Text(l10n.apply)),
                      ],
                    ),
                  ],
                  if (s.history.isNotEmpty) ...[
                    const SizedBox(height: 24),
                    Text(l10n.pointsHistory, style: AppTextStyles.subtitle1),
                    for (final e in s.history)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(_entryLabel(e)),
                        subtitle: Text(friendlyDateTime(e.createdAt, l10n: l10n)),
                        trailing: Text(
                          e.points > 0 ? '+${e.points}' : '${e.points}',
                          style: AppTextStyles.subtitle2.copyWith(color: e.points > 0 ? context.palette.success : context.colors.error),
                        ),
                      ),
                  ],
                ],
              ),
            ),
    );
  }
}
