import 'dart:async';

import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
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
    if (entryId == null) return;
    setState(() => _leaving = true);
    try {
      await _api.leave(queueId: widget.ticket.queueId, entryId: entryId);
      if (mounted) Navigator.pop(context);
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
    return Scaffold(
      appBar: AppBar(title: Text(widget.serviceName)),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const SizedBox(height: 24),
            if (ticket == null) ...[
              const Icon(Icons.check_circle, color: AppColors.success, size: 96),
              const SizedBox(height: 16),
              const Text(
                "You're no longer in this queue. Thanks for visiting!",
                textAlign: TextAlign.center,
                style: AppTextStyles.subtitle1,
              ),
            ] else if (ticket.isCalled) ...[
              const Icon(Icons.campaign, color: AppColors.success, size: 96),
              const SizedBox(height: 16),
              Text(
                "It's your turn!",
                textAlign: TextAlign.center,
                style: AppTextStyles.heading2.copyWith(color: AppColors.success),
              ),
              const SizedBox(height: 8),
              const Text(
                'Please go to the counter now.',
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
                    color: AppColors.primaryLight,
                    border: Border.all(color: AppColors.primary, width: 3),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '#${ticket.position}',
                        style: AppTextStyles.heading1.copyWith(color: AppColors.primary),
                      ),
                      const Text('Your Position', style: AppTextStyles.caption),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 32),
              const Text(
                'Estimated Wait Time',
                textAlign: TextAlign.center,
                style: AppTextStyles.subtitle1,
              ),
              const SizedBox(height: 8),
              Text(
                waitLabel(ticket),
                textAlign: TextAlign.center,
                style: AppTextStyles.heading2.copyWith(color: AppColors.accent),
              ),
              if (ticket.estimatedCallAt != null && (ticket.estimatedWaitMinutes ?? 0) > 0) ...[
                const SizedBox(height: 4),
                Text(
                  'Expected around ${TimeOfDay.fromDateTime(ticket.estimatedCallAt!).format(context)}',
                  textAlign: TextAlign.center,
                  style: AppTextStyles.body2,
                ),
              ],
              if (ticket.peopleAhead != null) ...[
                const SizedBox(height: 16),
                Text(
                  aheadLabel(ticket.peopleAhead!),
                  textAlign: TextAlign.center,
                  style: AppTextStyles.body2,
                ),
              ],
              const SizedBox(height: 16),
              const Text(
                "We'll notify you when you're almost up, so you don't need to wait here.",
                textAlign: TextAlign.center,
                style: AppTextStyles.caption,
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 16),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: AppTextStyles.caption.copyWith(color: AppColors.error),
              ),
            ],
            const SizedBox(height: 32),
            if (ticket != null && !ticket.isCalled && widget.ticket.entryId != null)
              CustomButton(
                label: 'Leave Queue',
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
String waitLabel(QueueTicket ticket) {
  final minutes = ticket.estimatedWaitMinutes;
  if (minutes == null) return 'Not available yet';
  if (minutes <= 0) return "You're next";
  return '$minutes min';
}

String aheadLabel(int peopleAhead) => switch (peopleAhead) {
      0 => 'Nobody is ahead of you',
      1 => '1 person ahead of you',
      _ => '$peopleAhead people ahead of you',
    };
