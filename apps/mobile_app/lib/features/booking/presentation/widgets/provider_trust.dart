import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/errors/exceptions.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../domain/entities/booking.dart';

/// The step that starts work at the customer's: IN_PROGRESS on a home visit, PICKED_UP for a pickup. It
/// needs the customer's 4-digit start code (booking_service refuses it without).
bool needsStartCode(String mode, String targetStatus) =>
    (mode == 'AT_HOME' && targetStatus == BookingStatus.inProgress) ||
    (mode == 'PICKUP_DROP' && targetStatus == BookingStatus.pickedUp);

/// What to tell the professional when the server refused the code: too many tries (429), or a wrong or
/// missing code (422, the server's own words when it sent them).
String startCodeError(Object error, AppLocalizations l10n) {
  if (error is ServerException) {
    if (error.statusCode == 429) return l10n.startCodeTooMany;
    if (error.statusCode == 422) return error.message.isEmpty ? l10n.startCodeWrong : error.message;
  }
  return apiErrorMessage(error);
}

/// Asks for the customer's start code and runs [submit] with it; stays open with the reason while the
/// server refuses it. Pops true once the job has started.
Future<bool> askStartCode(BuildContext context, Future<void> Function(String code) submit) async =>
    await showDialog<bool>(context: context, builder: (_) => _StartCodeDialog(submit: submit)) ?? false;

class _StartCodeDialog extends StatefulWidget {
  final Future<void> Function(String code) submit;

  const _StartCodeDialog({required this.submit});

  @override
  State<_StartCodeDialog> createState() => _StartCodeDialogState();
}

class _StartCodeDialogState extends State<_StartCodeDialog> {
  final _code = TextEditingController();
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    final l10n = context.l10n;
    final code = _code.text.trim();
    if (!RegExp(r'^\d{4}$').hasMatch(code)) {
      setState(() => _error = l10n.startCodeWrong);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.submit(code);
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => _error = startCodeError(e, l10n));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return AlertDialog(
      title: Text(l10n.startJobTitle),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.startCodeAsk),
          const SizedBox(height: 12),
          TextField(
            key: const ValueKey('start-code-field'),
            controller: _code,
            autofocus: true,
            keyboardType: TextInputType.number,
            maxLength: 4,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            style: AppTextStyles.heading2.copyWith(letterSpacing: 8, color: context.colors.onSurface),
            decoration: InputDecoration(labelText: l10n.startCodeLabel, errorText: _error, errorMaxLines: 3),
            onSubmitted: (_) => _busy ? null : _start(),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: _busy ? null : () => Navigator.pop(context, false), child: Text(l10n.notNow)),
        FilledButton(
          key: const ValueKey('start-code-submit'),
          onPressed: _busy ? null : _start,
          child: _busy
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : Text(l10n.startCodeStart),
        ),
      ],
    );
  }
}

/// A small "Free fix" label for a booking that redoes an earlier one at no cost.
class FreeFixChip extends StatelessWidget {
  const FreeFixChip({super.key});

  @override
  Widget build(BuildContext context) {
    final color = context.palette.info;
    return Container(
      key: const ValueKey('free-fix-chip'),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(8)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.build_circle_outlined, size: 14, color: color),
        const SizedBox(width: 4),
        Text(context.l10n.freeFixLabel, style: AppTextStyles.caption.copyWith(color: color, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}
