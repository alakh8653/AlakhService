import 'dart:async';

import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../l10n/l10n.dart';
import '../../data/queue_api.dart';

/// The customer's live place in a walk-in queue.
class QueueStatusPage extends StatefulWidget {
  final QueueTicket ticket;
  final String customerId;
  final String serviceName;
  final QueueApi? queueApi;
  final Duration pollInterval;

  const QueueStatusPage({
    super.key,
    required this.ticket,
    required this.customerId,
    required this.serviceName,
    this.queueApi,
    this.pollInterval = const Duration(seconds: 15),
  });

  @override
  State<QueueStatusPage> createState() => _QueueStatusPageState();
}

class _QueueStatusPageState extends State<QueueStatusPage> {
  late final QueueApi _api = widget.queueApi ?? sl<QueueApi>();
  late QueueTicket? _ticket = widget.ticket;
  Timer? _timer;
  String? _error;
  bool _leaving = false;

  @override
  void initState() {
    super.initState();
    // The join response has no people-ahead or call time; fetch the full picture straight away.
    _refresh();
    _timer = Timer.periodic(widget.pollInterval, (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final ticket = await _api.position(
        queueId: widget.ticket.queueId,
        customerId: widget.customerId,
      );
      if (!mounted) return;
      setState(() {
        _ticket = ticket;
        _error = null;
      });
      if (ticket == null) _timer?.cancel();
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  Future<void> _leave() async {
    final entryId = widget.ticket.entryId;
    if (entryId == null || _leaving) return;
    final l10n = context.l10n;
    final sure = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.queueLeaveQuestion),
        content: Text(l10n.queueLeaveBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(l10n.queueStay)),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: TextButton.styleFrom(foregroundColor: context.colors.error),
            child: Text(l10n.queueLeave),
          ),
        ],
      ),
    );
    if (sure != true || !mounted) return;
    setState(() => _leaving = true);
    try {
      await _api.leave(queueId: widget.ticket.queueId, entryId: entryId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l10n.queueLeft)));
      Navigator.pop(context);
    } catch (e) {
      if (!mounted) return;
      setState(() => _leaving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final ticket = _ticket;
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(widget.serviceName)),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const SizedBox(height: 24),
            if (ticket == null) ...[
              Icon(Icons.check_circle, color: context.palette.success, size: 96),
              const SizedBox(height: 16),
              Text(
                l10n.queueNoLonger,
                textAlign: TextAlign.center,
                style: AppTextStyles.subtitle1,
              ),
              const SizedBox(height: 24),
              CustomButton(label: l10n.done, onPressed: () => Navigator.pop(context)),
            ] else if (ticket.isCalled) ...[
              Icon(Icons.campaign, color: context.palette.success, size: 96),
              const SizedBox(height: 16),
              Semantics(
                liveRegion: true,
                child: Text(
                l10n.queueYourTurn,
                textAlign: TextAlign.center,
                style: AppTextStyles.heading2.copyWith(color: context.palette.success),
              ),
              ),
              const SizedBox(height: 8),
              Text(
                l10n.queueGoToCounter,
                textAlign: TextAlign.center,
                style: AppTextStyles.subtitle1,
              ),
            ] else ...[
              Center(
                child: Container(
                  width: 160,
                  height: 160,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: context.colors.primaryContainer,
                    border: Border.all(color: context.colors.primary, width: 3),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '#${ticket.position}',
                        semanticsLabel: l10n.queuePositionSemantics(ticket.position),
                        style: AppTextStyles.heading1.copyWith(color: context.colors.primary),
                      ),
                      Text(l10n.queueYourPosition, style: AppTextStyles.caption.themed(context)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 32),
              Text(
                l10n.queueEstimatedWait,
                textAlign: TextAlign.center,
                style: AppTextStyles.subtitle1,
              ),
              const SizedBox(height: 8),
              Text(
                waitLabel(ticket, l10n: l10n),
                textAlign: TextAlign.center,
                style: AppTextStyles.heading2.copyWith(color: AppColors.accent),
              ),
              if (ticket.estimatedCallAt != null && (ticket.estimatedWaitMinutes ?? 0) > 0) ...[
                const SizedBox(height: 4),
                Text(
                  l10n.queueExpectedAround(clockTime(ticket.estimatedCallAt!)),
                  textAlign: TextAlign.center,
                  style: AppTextStyles.body2.themed(context),
                ),
              ],
              if (ticket.peopleAhead != null) ...[
                const SizedBox(height: 16),
                Text(
                  aheadLabel(ticket.peopleAhead!, l10n: l10n),
                  textAlign: TextAlign.center,
                  style: AppTextStyles.body2.themed(context),
                ),
              ],
              const SizedBox(height: 16),
              Text(
                l10n.queueWeWillNotify,
                textAlign: TextAlign.center,
                style: AppTextStyles.caption.themed(context),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 16),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: AppTextStyles.caption.copyWith(color: context.colors.error),
              ),
            ],
            const SizedBox(height: 32),
            if (ticket != null && !ticket.isCalled && widget.ticket.entryId != null)
              CustomButton(
                label: l10n.queueLeaveButton,
                variant: ButtonVariant.secondary,
                onPressed: _leaving ? null : _leave,
                isLoading: _leaving,
              ),
          ],
        ),
      ),
    );
  }
}

/// "12 min", or "You're next" when there is no wait left.
String waitLabel(QueueTicket ticket, {AppLocalizations? l10n}) {
  l10n ??= currentL10n;
  final minutes = ticket.estimatedWaitMinutes;
  if (minutes == null) return l10n.queueWaitUnknown;
  if (minutes <= 0) return l10n.queueYoureNext;
  return l10n.queueWaitMinutes(minutes);
}

String aheadLabel(int peopleAhead, {AppLocalizations? l10n}) => (l10n ?? currentL10n).queueAhead(peopleAhead);
