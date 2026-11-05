import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/utils/format.dart';
import '../../data/trust_api.dart';
import '../../domain/entities/booking.dart';

/// The 4-digit code the customer gives the professional on arrival, big enough to read out.
class StartCodeCard extends StatelessWidget {
  final String code;

  const StartCodeCard({super.key, required this.code});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Container(
      key: const ValueKey('start-code'),
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: context.colors.primaryContainer,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(children: [
        Icon(Icons.pin_outlined, color: context.colors.onPrimaryContainer),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(l10n.startCodeTitle, style: AppTextStyles.caption.copyWith(color: context.colors.onPrimaryContainer)),
            Semantics(
              label: code.split('').join(' '),
              child: ExcludeSemantics(
                child: Text(
                  code,
                  style: AppTextStyles.heading1.copyWith(color: context.colors.onPrimaryContainer, letterSpacing: 8),
                ),
              ),
            ),
            Text(l10n.startCodeHelp, style: AppTextStyles.body2.copyWith(color: context.colors.onPrimaryContainer)),
          ]),
        ),
      ]),
    );
  }
}

/// The shop's free-fix guarantee on a completed booking, the request for it, and the links between a
/// booking and its free fix.
class FreeFixSection extends StatelessWidget {
  final Booking booking;
  final DateTime now;
  final ValueChanged<String> onOpenBooking;
  final VoidCallback onRequest;

  const FreeFixSection({
    super.key,
    required this.booking,
    required this.now,
    required this.onOpenBooking,
    required this.onRequest,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final until = booking.guaranteeUntil;
    final children = <Widget>[
      if (booking.reworkOf != null) ...[
        _line(context, Icons.build_circle_outlined, l10n.reworkOf, context.palette.info),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(onPressed: () => onOpenBooking(booking.reworkOf!), child: Text(l10n.reworkOpenOriginal)),
        ),
      ],
      if (booking.reworkOf == null && booking.status == BookingStatus.completed && until != null)
        _line(
          context,
          Icons.verified_outlined,
          now.isBefore(until) ? l10n.guaranteeUntil(friendlyDay(until, now: now, l10n: l10n)) : l10n.guaranteeEnded(friendlyDay(until, now: now, l10n: l10n)),
          now.isBefore(until) ? context.palette.success : context.palette.muted,
        ),
      if (booking.reworkBookingId != null)
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            icon: const Icon(Icons.build_circle_outlined, size: 18),
            onPressed: () => onOpenBooking(booking.reworkBookingId!),
            label: Text(l10n.reworkOpen),
          ),
        )
      else if (booking.canRequestRework(now))
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            key: const ValueKey('request-rework'),
            onPressed: onRequest,
            icon: const Icon(Icons.handyman_outlined),
            label: Text(l10n.reworkRequest),
          ),
        ),
    ];
    if (children.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children);
  }

  Widget _line(BuildContext context, IconData icon, String text, Color color) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(icon, size: 20, color: color),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: AppTextStyles.body2.copyWith(color: color))),
        ]),
      );
}

/// The customer says what went wrong, and when suits them; pops with the free-fix booking's id.
class ReworkRequestPage extends StatefulWidget {
  final Booking booking;
  final TrustApi? api;
  final DateTime Function() clock;

  const ReworkRequestPage({super.key, required this.booking, this.api, this.clock = DateTime.now});

  @override
  State<ReworkRequestPage> createState() => _ReworkRequestPageState();
}

class _ReworkRequestPageState extends State<ReworkRequestPage> {
  final _form = GlobalKey<FormState>();
  final _reason = TextEditingController();
  DateTime? _preferred;
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _pickTime() async {
    final now = widget.clock();
    final day = await showDatePicker(
      context: context,
      initialDate: now.add(const Duration(days: 1)),
      firstDate: now,
      lastDate: now.add(const Duration(days: 30)),
    );
    if (day == null || !mounted) return;
    final time = await showTimePicker(context: context, initialTime: const TimeOfDay(hour: 10, minute: 0));
    if (time == null || !mounted) return;
    setState(() => _preferred = DateTime(day.year, day.month, day.day, time.hour, time.minute));
  }

  Future<void> _send() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final id = await (widget.api ?? sl<TrustApi>())
          .requestRework(widget.booking.id, reason: _reason.text, preferredAt: _preferred);
      if (mounted) Navigator.pop(context, id);
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.reworkTitle)),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _form,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(widget.booking.serviceName, style: AppTextStyles.heading3),
                const SizedBox(height: 8),
                Text(l10n.reworkExplain, style: AppTextStyles.body2.themed(context)),
                const SizedBox(height: 16),
                TextFormField(
                  key: const ValueKey('rework-reason'),
                  controller: _reason,
                  maxLines: 4,
                  maxLength: 500,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: InputDecoration(labelText: l10n.reworkReason, alignLabelWithHint: true),
                  validator: (v) => (v ?? '').trim().length < 10 ? l10n.reworkReasonShort : null,
                ),
                const SizedBox(height: 8),
                Text(l10n.reworkPreferred, style: AppTextStyles.caption.themed(context)),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    icon: const Icon(Icons.schedule),
                    onPressed: _sending ? null : _pickTime,
                    label: Text(_preferred == null ? l10n.reworkPickTime : friendlyDateTime(_preferred!, l10n: l10n)),
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 8),
                  Text(_error!, style: AppTextStyles.body2.copyWith(color: context.colors.error)),
                ],
                const SizedBox(height: 16),
                FilledButton(
                  key: const ValueKey('rework-send'),
                  onPressed: _sending ? null : _send,
                  child: _sending
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(l10n.reworkSend),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
