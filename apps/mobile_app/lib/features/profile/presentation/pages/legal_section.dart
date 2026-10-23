import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/utils/format.dart';
import '../../../directions/presentation/how_to_get_there_sheet.dart' show LinkOpener, openExternally;
import '../../../legal/data/legal_api.dart';
import '../../data/data_export_api.dart';

/// Profile's Legal section (Terms, Privacy, Refunds, Grievance, opened in the browser) and
/// "Download my data" with the state of the latest request.
class LegalSection extends StatefulWidget {
  final String userId;
  final LegalApi? legalApi;
  final DataExportApi? dataExportApi;
  final LinkOpener? open;

  const LegalSection({super.key, required this.userId, this.legalApi, this.dataExportApi, this.open});

  @override
  State<LegalSection> createState() => _LegalSectionState();
}

class _LegalSectionState extends State<LegalSection> {
  LegalInfo _legal = LegalInfo.fallback;
  DataExportRequest? _export;
  bool _requesting = false;

  DataExportApi get _exports => widget.dataExportApi ?? sl<DataExportApi>();

  @override
  void initState() {
    super.initState();
    (widget.legalApi ?? sl<LegalApi>()).current().then((info) {
      if (mounted) setState(() => _legal = info);
    });
    _loadExport();
  }

  Future<void> _loadExport() async {
    try {
      final latest = await _exports.latest();
      if (mounted) setState(() => _export = latest);
    } catch (_) {
      // The tile still offers a new request.
    }
  }

  void _open(String url) => (widget.open ?? openExternally)(Uri.parse(url)).catchError((Object _) => false);

  Future<void> _onDownloadTap() async {
    final export = _export;
    if (export != null && export.isReady) return _open(export.exportUrl!);
    if (export != null && export.isPending) return;
    final l10n = context.l10n;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.dataExportQuestion),
        content: Text(l10n.dataExportBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(l10n.cancel)),
          TextButton(onPressed: () => Navigator.pop(dialogContext, true), child: Text(l10n.dataExportRequest)),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _requesting = true);
    try {
      final request = await _exports.request(widget.userId);
      if (!mounted) return;
      setState(() => _export = request);
      messenger.showSnackBar(SnackBar(content: Text(l10n.dataExportRequested), backgroundColor: AppColors.success));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    } finally {
      if (mounted) setState(() => _requesting = false);
    }
  }

  String _exportStatus(AppLocalizations l10n) {
    final export = _export;
    if (export == null) return l10n.dataExportNone;
    if (export.isReady) return l10n.dataExportReady;
    if (export.isPending) return l10n.dataExportPending(friendlyDay(export.requestedAt, l10n: l10n));
    return export.note == null || export.note!.isEmpty
        ? l10n.dataExportDeclined
        : '${l10n.dataExportDeclined} ${export.note}';
  }

  Widget _link(IconData icon, String label, String url) => ListTile(
        leading: Icon(icon, color: context.palette.muted),
        title: Text(label, style: AppTextStyles.body1),
        trailing: Icon(Icons.open_in_new, size: 18, color: context.palette.muted),
        onTap: () => _open(url),
        contentPadding: EdgeInsets.zero,
      );

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 16, bottom: 4),
          child: Semantics(
            header: true,
            child: Text(l10n.legalSection, style: AppTextStyles.subtitle2.copyWith(color: context.colors.onSurface)),
          ),
        ),
        _link(Icons.description_outlined, l10n.termsOfService, _legal.termsUrl),
        _link(Icons.privacy_tip_outlined, l10n.privacyPolicy, _legal.privacyUrl),
        _link(Icons.currency_rupee, l10n.refundPolicy, _legal.refundUrl),
        _link(Icons.support_agent, l10n.grievanceOfficer, _legal.grievanceUrl),
        ListTile(
          leading: Icon(Icons.download_outlined, color: context.palette.muted),
          title: Text(l10n.downloadMyData, style: AppTextStyles.body1),
          subtitle: Text(_exportStatus(l10n), style: AppTextStyles.caption.themed(context)),
          trailing: _requesting
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : Icon(_export?.isReady == true ? Icons.open_in_new : Icons.chevron_right, color: context.palette.muted),
          onTap: _requesting ? null : _onDownloadTap,
          contentPadding: EdgeInsets.zero,
        ),
      ],
    );
  }
}
