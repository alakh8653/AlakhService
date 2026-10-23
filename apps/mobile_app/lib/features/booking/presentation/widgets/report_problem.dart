import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../l10n/l10n.dart';
import '../../data/dispute_api.dart';
import '../../domain/entities/booking.dart';

/// [disputeTypes]' kinds of problem in the language on screen.
String disputeTypeLabel(AppLocalizations l10n, String type) => switch (type) {
      'service_quality' => l10n.disputeServiceQuality,
      'no_show' => l10n.disputeNoShow,
      'damage' => l10n.disputeDamage,
      'billing' => l10n.disputeBilling,
      'other' => l10n.disputeOther,
      _ => disputeTypes[type] ?? type,
    };

/// Asks what went wrong with [booking] and reports it to Alakh support (dispute_service). True once
/// reported; false if the customer backed out or it could not be sent (they are told why).
Future<bool> reportBookingProblem(BuildContext context, Booking booking, {DisputeApi? api}) async {
  final report = await showDialog<(String, String)>(context: context, builder: (_) => const ReportProblemDialog());
  if (report == null || !context.mounted) return false;
  final messenger = ScaffoldMessenger.of(context);
  final l10n = context.l10n;
  try {
    await (api ?? sl<DisputeApi>()).report(bookingId: booking.id, type: report.$1, description: report.$2);
    messenger.showSnackBar(SnackBar(content: Text(l10n.reportThanks)));
    return true;
  } catch (e) {
    messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    return false;
  }
}

/// Asks what went wrong; pops with (type, description).
class ReportProblemDialog extends StatefulWidget {
  const ReportProblemDialog({super.key});

  @override
  State<ReportProblemDialog> createState() => _ReportProblemDialogState();
}

class _ReportProblemDialogState extends State<ReportProblemDialog> {
  String _type = disputeTypes.keys.first;
  final _description = TextEditingController();

  @override
  void dispose() {
    _description.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final valid = _description.text.trim().length >= 3;
    return AlertDialog(
      title: Text(l10n.reportProblem),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DropdownButtonFormField<String>(
              initialValue: _type,
              isExpanded: true,
              items: [
                for (final type in disputeTypes.keys)
                  DropdownMenuItem(value: type, child: Text(disputeTypeLabel(l10n, type))),
              ],
              onChanged: (v) => setState(() => _type = v ?? _type),
              decoration: InputDecoration(labelText: l10n.whatWentWrong),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _description,
              maxLines: 4,
              maxLength: 2000,
              textCapitalization: TextCapitalization.sentences,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                labelText: l10n.tellWhatHappened,
                helperText: l10n.atLeast3,
                alignLabelWithHint: true,
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(l10n.cancel)),
        TextButton(
          onPressed: valid ? () => Navigator.pop(context, (_type, _description.text.trim())) : null,
          child: Text(l10n.send),
        ),
      ],
    );
  }
}
