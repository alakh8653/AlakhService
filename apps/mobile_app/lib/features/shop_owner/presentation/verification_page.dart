import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/widgets/custom_button.dart';
import '../../../shared/widgets/custom_text_field.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../data/shop_owner_api.dart';

/// Takes a photo or picks one; null when the person backs out.
typedef PickDocument = Future<PickedDocument?> Function(ImageSource source);

Future<PickedDocument?> pickDocumentPhoto(ImageSource source) async {
  // Small enough to upload on mobile data, and well under the 5 MB limit, while staying readable.
  final file = await ImagePicker().pickImage(source: source, maxWidth: 2000, maxHeight: 2000, imageQuality: 75);
  if (file == null) return null;
  final name = file.name.toLowerCase();
  final type = name.endsWith('.png')
      ? 'image/png'
      : name.endsWith('.webp')
          ? 'image/webp'
          : 'image/jpeg';
  return PickedDocument(await file.readAsBytes(), type, file.name);
}

/// Picks a PDF; null when the person backs out.
typedef PickPdf = Future<PickedDocument?> Function();

Future<PickedDocument?> pickDocumentPdf() async {
  final picked = await FilePicker.pickFiles(type: FileType.custom, allowedExtensions: const ['pdf']);
  if (picked.isEmpty) return null;
  final file = picked.single;
  return PickedDocument(await file.readAsBytes(), 'application/pdf', file.name);
}

/// Who runs the business, proof of it, and where to send their money; then the admins review it. Photos
/// come straight from the camera, since most people here will not have scans.
class VerificationPage extends StatefulWidget {
  final String shopId;
  final bool firstTime;
  final ShopOwnerApi? api;
  final PickDocument? pickDocument;
  final PickPdf? pickPdf;

  const VerificationPage({
    super.key,
    required this.shopId,
    this.firstTime = false,
    this.api,
    this.pickDocument,
    this.pickPdf,
  });

  @override
  State<VerificationPage> createState() => _VerificationPageState();
}

class _VerificationPageState extends State<VerificationPage> {
  static const _pdf = 'pdf';
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  final _form = GlobalKey<FormState>();
  final _legalName = TextEditingController();
  final _legalAddress = TextEditingController();
  final _gstin = TextEditingController();
  final _upi = TextEditingController();
  final _accountName = TextEditingController();
  final _accountNumber = TextEditingController();
  final _ifsc = TextEditingController();
  OwnerShop? _shop;
  Set<String> _documents = {};
  List<ChecklistItem> _checklist = const [];
  PayoutDetails? _payout;
  String _payoutMethod = 'UPI';
  String? _uploading;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final c in [_legalName, _legalAddress, _gstin, _upi, _accountName, _accountNumber, _ifsc]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final shop = await _api.shop(widget.shopId);
      final documents = await _api.documentTypes(widget.shopId);
      final checklist = await _api.checklist(widget.shopId);
      final payout = await _api.payoutDetails(widget.shopId);
      if (!mounted) return;
      _legalName.text = shop.legalName ?? '';
      _legalAddress.text = shop.legalAddress ?? '';
      _gstin.text = shop.gstin ?? '';
      setState(() {
        _shop = shop;
        _documents = documents;
        _checklist = checklist;
        _payout = payout;
        _payoutMethod = payout?.method ?? 'UPI';
      });
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _upload(String type) async {
    final l10n = context.l10n;
    // A photo source, or _pdf.
    final source = await showModalBottomSheet<Object>(
      context: context,
      builder: (sheet) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined),
              title: Text(l10n.ownerTakePhoto),
              onTap: () => Navigator.pop(sheet, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: Text(l10n.ownerChoosePhoto),
              onTap: () => Navigator.pop(sheet, ImageSource.gallery),
            ),
            ListTile(
              leading: const Icon(Icons.picture_as_pdf_outlined),
              title: Text(l10n.ownerChoosePdf),
              onTap: () => Navigator.pop(sheet, _pdf),
            ),
          ],
        ),
      ),
    );
    if (source == null) return;
    setState(() {
      _uploading = type;
      _error = null;
    });
    try {
      final file = source == _pdf
          ? await (widget.pickPdf ?? pickDocumentPdf)()
          : await (widget.pickDocument ?? pickDocumentPhoto)(source as ImageSource);
      if (file == null) return;
      await _api.uploadDocument(widget.shopId, type, file);
      if (mounted) setState(() => _documents = {..._documents, type});
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = l10n.ownerPhotoFailed);
    } finally {
      if (mounted) setState(() => _uploading = null);
    }
  }

  /// Not sent yet, and why: beside the button, and where they can see it wherever they have scrolled to.
  void _blocked(String why) {
    setState(() => _error = why);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(why)));
  }

  Future<void> _submit() async {
    final l10n = context.l10n;
    final shop = _shop;
    if (shop == null || !(_form.currentState?.validate() ?? false)) return;
    if (!_documents.contains('PAN')) {
      _blocked(l10n.ownerPanNeeded);
      return;
    }
    for (final item in _checklist) {
      if (item.required && !_documents.contains(item.type)) {
        _blocked(l10n.ownerDocNeeded(item.label));
        return;
      }
    }
    final gstin = _gstin.text.trim();
    if (gstin.isNotEmpty && !_documents.contains('GST')) {
      _blocked(l10n.ownerGstNeeded);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await _api.saveLegalDetails(
        widget.shopId,
        legalName: _legalName.text.trim(),
        legalAddress: _legalAddress.text.trim(),
        gstin: gstin,
      );
      final upi = _upi.text.trim(), number = _accountNumber.text.trim();
      if (_payoutMethod == 'UPI' && upi.isNotEmpty) {
        await _api.savePayoutDetails(widget.shopId, method: 'UPI', upiId: upi, accountName: _accountName.text.trim());
      } else if (_payoutMethod == 'BANK' && number.isNotEmpty) {
        await _api.savePayoutDetails(
          widget.shopId,
          method: 'BANK',
          accountName: _accountName.text.trim(),
          accountNumber: number,
          ifsc: _ifsc.text.trim(),
        );
      }
      final saved = shop.approved ? shop : await _api.submitForReview(widget.shopId);
      if (!mounted) return;
      setState(() {
        _shop = saved;
        _saving = false;
      });
      if (shop.approved) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l10n.ownerDetailsSaved)));
      } else {
        // Said plainly and waited on, so nobody is left wondering whether it was sent.
        await showDialog<void>(
          context: context,
          builder: (dialog) => AlertDialog(
            icon: const Icon(Icons.check_circle, color: AppColors.success, size: 40),
            title: Text(l10n.ownerSubmittedTitle),
            content: Text(l10n.ownerSubmitted),
            actions: [FilledButton(onPressed: () => Navigator.pop(dialog), child: Text(l10n.done))],
          ),
        );
      }
      if (mounted) Navigator.pop(context);
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _status(OwnerShop shop, AppLocalizations l10n) {
    final (IconData icon, Color color, String text) = shop.approved
        ? (Icons.verified, AppColors.success, l10n.ownerStatusApproved)
        : shop.rejected
            ? (Icons.error_outline, AppColors.error, l10n.ownerStatusRejected(shop.rejectionReason ?? ''))
            : shop.waitingForReview
                ? (Icons.hourglass_top, AppColors.warning, l10n.ownerStatusInReview)
                : (Icons.info_outline, AppColors.primary, l10n.ownerStatusNotSubmitted);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: color),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: AppTextStyles.body2.themed(context))),
      ],
    );
  }

  Widget _todo(String label, bool done) => Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Row(
          children: [
            Icon(
              done ? Icons.check_circle : Icons.radio_button_unchecked,
              size: 20,
              color: done ? AppColors.success : context.palette.muted,
            ),
            const SizedBox(width: 8),
            Expanded(child: Text(label, style: AppTextStyles.body2.themed(context))),
          ],
        ),
      );

  Widget _document(String type, String label, {bool required = false}) {
    final l10n = context.l10n;
    final done = _documents.contains(type);
    return ListTile(
      key: ValueKey('document-$type'),
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        done ? Icons.check_circle : Icons.badge_outlined,
        color: done ? AppColors.success : context.palette.muted,
      ),
      title: Text(label, style: AppTextStyles.body1),
      subtitle: Text(done ? l10n.ownerUploaded : (required ? l10n.ownerNeeded : l10n.ownerOptional)),
      trailing: _uploading == type
          ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2))
          : TextButton(
              onPressed: _uploading == null ? () => _upload(type) : null,
              child: Text(done ? l10n.ownerReplace : l10n.ownerAddPhoto),
            ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final shop = _shop;
    final payout = _payout;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.ownerVerificationTitle)),
      body: _loading
          ? const LoadingIndicator()
          : shop == null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(_error ?? '', textAlign: TextAlign.center),
                        const SizedBox(height: 12),
                        TextButton(onPressed: _load, child: Text(l10n.retry)),
                      ],
                    ),
                  ),
                )
              : SafeArea(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(20),
                    child: Form(
                      key: _form,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          _status(shop, l10n),
                          if (!shop.approved && !shop.waitingForReview) ...[
                            const SizedBox(height: 16),
                            Text(l10n.ownerBeforeSending, style: AppTextStyles.body1),
                            _todo(l10n.ownerLegalName, _legalName.text.trim().isNotEmpty),
                            _todo(l10n.ownerDocPan, _documents.contains('PAN')),
                            if (_gstin.text.trim().isNotEmpty) _todo(l10n.ownerDocGst, _documents.contains('GST')),
                            _todo(l10n.ownerSubmit, false),
                          ],
                          const SizedBox(height: 24),
                          Text(l10n.ownerAboutYou, style: AppTextStyles.heading3),
                          const SizedBox(height: 12),
                          CustomTextField(
                            controller: _legalName,
                            label: l10n.ownerLegalName,
                            helper: l10n.ownerLegalNameHelp,
                            textCapitalization: TextCapitalization.words,
                            onChanged: (_) => setState(() {}),
                            validator: (v) => (v ?? '').trim().isEmpty ? l10n.ownerRequired : null,
                          ),
                          const SizedBox(height: 12),
                          CustomTextField(
                            controller: _legalAddress,
                            label: l10n.ownerLegalAddress,
                            maxLines: 2,
                            textCapitalization: TextCapitalization.sentences,
                          ),
                          const SizedBox(height: 12),
                          CustomTextField(
                            controller: _gstin,
                            label: l10n.ownerGstin,
                            helper: l10n.ownerGstinHelp,
                            textCapitalization: TextCapitalization.characters,
                            onChanged: (_) => setState(() {}),
                          ),
                          const SizedBox(height: 24),
                          Text(l10n.ownerDocuments, style: AppTextStyles.heading3),
                          Text(l10n.ownerDocumentsHelp, style: AppTextStyles.caption.themed(context)),
                          _document('PAN', l10n.ownerDocPan, required: true),
                          for (final item in _checklist.where((i) => i.required))
                            _document(item.type, item.label, required: true),
                          if (_gstin.text.trim().isNotEmpty) _document('GST', l10n.ownerDocGst, required: true),
                          for (final item in _checklist.where((i) => !i.required)) _document(item.type, item.label),
                          _document('AADHAAR', l10n.ownerDocAadhaar),
                          _document('SHOP_PHOTO', l10n.ownerDocShopPhoto),
                          const SizedBox(height: 24),
                          Text(l10n.ownerPayouts, style: AppTextStyles.heading3),
                          const SizedBox(height: 4),
                          Text(l10n.ownerPayoutsHelp, style: AppTextStyles.caption.themed(context)),
                          const SizedBox(height: 12),
                          SegmentedButton<String>(
                            segments: [
                              ButtonSegment(value: 'UPI', label: Text(l10n.ownerUpi)),
                              ButtonSegment(value: 'BANK', label: Text(l10n.ownerBankAccount)),
                            ],
                            selected: {_payoutMethod},
                            onSelectionChanged: (s) => setState(() => _payoutMethod = s.first),
                          ),
                          const SizedBox(height: 12),
                          if (payout != null) ...[
                            Text(
                              l10n.ownerPayoutSaved(payout.upiId ?? payout.accountNumber ?? ''),
                              style: AppTextStyles.caption.themed(context),
                            ),
                            const SizedBox(height: 12),
                          ],
                          if (_payoutMethod == 'UPI')
                            CustomTextField(
                              controller: _upi,
                              label: l10n.ownerUpiId,
                              hint: 'name@upi',
                              keyboardType: TextInputType.emailAddress,
                            )
                          else ...[
                            CustomTextField(
                              controller: _accountName,
                              label: l10n.ownerAccountName,
                              textCapitalization: TextCapitalization.words,
                            ),
                            const SizedBox(height: 12),
                            CustomTextField(
                              controller: _accountNumber,
                              label: l10n.ownerAccountNumber,
                              keyboardType: TextInputType.number,
                            ),
                            const SizedBox(height: 12),
                            CustomTextField(
                              controller: _ifsc,
                              label: l10n.ownerIfsc,
                              textCapitalization: TextCapitalization.characters,
                            ),
                          ],
                          if (_error != null) ...[
                            const SizedBox(height: 12),
                            Text(_error!, style: AppTextStyles.body2.copyWith(color: AppColors.error)),
                          ],
                          const SizedBox(height: 24),
                          CustomButton(
                            label: shop.approved
                                ? l10n.save
                                : shop.rejected
                                    ? l10n.ownerSubmitAgain
                                    : l10n.ownerSubmit,
                            isLoading: _saving,
                            onPressed: _saving ? null : _submit,
                          ),
                          if (widget.firstTime) ...[
                            const SizedBox(height: 8),
                            TextButton(onPressed: () => Navigator.pop(context), child: Text(l10n.ownerDoItLater)),
                          ],
                        ],
                      ),
                    ),
                  ),
                ),
    );
  }
}
