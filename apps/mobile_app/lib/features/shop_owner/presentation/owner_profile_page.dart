import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../../shops/data/shop_profile_api.dart';
import '../data/shop_owner_api.dart';
import 'verification_page.dart';

/// Languages to tap on, in English as the rest of the catalogue is.
const profileLanguages = [
  'Hindi',
  'English',
  'Bengali',
  'Marathi',
  'Telugu',
  'Tamil',
  'Gujarati',
  'Urdu',
  'Kannada',
  'Odia',
  'Malayalam',
  'Punjabi',
];

/// What customers see before booking: experience, languages, a few words and photos of the work.
class OwnerProfilePage extends StatefulWidget {
  final String shopId;
  final ShopOwnerApi? api;
  final ShopProfileApi? profileApi;
  final PickDocument? pickPhoto;

  const OwnerProfilePage({super.key, required this.shopId, this.api, this.profileApi, this.pickPhoto});

  @override
  State<OwnerProfilePage> createState() => _OwnerProfilePageState();
}

class _OwnerProfilePageState extends State<OwnerProfilePage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  late final ShopProfileApi _profileApi = widget.profileApi ?? sl<ShopProfileApi>();
  final _about = TextEditingController();
  final _years = TextEditingController();
  Set<String> _languages = {};
  List<WorkPhoto> _photos = const [];
  bool _loading = true;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _about.dispose();
    _years.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final profile = await _profileApi.profile(widget.shopId);
      if (!mounted) return;
      setState(() {
        _about.text = profile.about ?? '';
        _years.text = profile.yearsExperience?.toString() ?? '';
        _languages = profile.languages.toSet();
        _photos = profile.photos;
        _loading = false;
        _error = null;
      });
    } on ServerException catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = e.message;
        });
      }
    }
  }

  Future<void> _run(Future<void> Function() change, {String? done}) async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await change();
      if (done != null) messenger.showSnackBar(SnackBar(content: Text(done)));
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() {
    final l10n = context.l10n;
    final years = _years.text.trim();
    return _run(
      () => _api.saveProfile(
        widget.shopId,
        about: _about.text.trim(),
        yearsExperience: years.isEmpty ? null : int.parse(years),
        languages: _languages.toList(),
      ),
      done: l10n.profileSaved,
    );
  }

  Future<void> _addPhoto() async {
    final l10n = context.l10n;
    final source = await showModalBottomSheet<ImageSource>(
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
          ],
        ),
      ),
    );
    if (source == null || !mounted) return;
    final file = await (widget.pickPhoto ?? pickDocumentPhoto)(source);
    if (file == null || !mounted) return;
    await _run(() async {
      await _api.addWorkPhoto(widget.shopId, file);
      await _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.ownerProfileTitle)),
      body: _loading
          ? const LoadingIndicator()
          : SafeArea(
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(l10n.profileHelp, style: AppTextStyles.body2.themed(context)),
                  const SizedBox(height: 16),
                  TextField(
                    key: const ValueKey('profile-years'),
                    controller: _years,
                    keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(2)],
                    decoration: InputDecoration(labelText: l10n.profileYearsLabel),
                  ),
                  const SizedBox(height: 16),
                  Text(l10n.profileLanguagesLabel, style: AppTextStyles.body2.themed(context)),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 8,
                    children: [
                      for (final language in profileLanguages)
                        FilterChip(
                          label: Text(language),
                          selected: _languages.contains(language),
                          onSelected: (on) => setState(() {
                            on ? _languages.add(language) : _languages.remove(language);
                          }),
                        ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    key: const ValueKey('profile-about'),
                    controller: _about,
                    maxLines: 3,
                    maxLength: 1000,
                    decoration: InputDecoration(labelText: l10n.profileAboutLabel, helperText: l10n.profileAboutHelp),
                  ),
                  if (_error != null) Text(_error!, style: AppTextStyles.body2.copyWith(color: AppColors.error)),
                  const SizedBox(height: 8),
                  FilledButton(
                    style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                    onPressed: _busy ? null : _save,
                    child: Text(l10n.save),
                  ),
                  const SizedBox(height: 24),
                  Text(l10n.profilePhotosTitle, style: AppTextStyles.heading3),
                  const SizedBox(height: 4),
                  Text(l10n.profilePhotosHelp, style: AppTextStyles.caption.themed(context)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final photo in _photos)
                        Stack(
                          children: [
                            ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: Image.network(
                                photo.url,
                                width: 100,
                                height: 100,
                                fit: BoxFit.cover,
                                cacheWidth: 300,
                                errorBuilder: (_, __, ___) => const SizedBox(
                                  width: 100,
                                  height: 100,
                                  child: Icon(Icons.image_not_supported_outlined),
                                ),
                              ),
                            ),
                            if (photo.isHidden)
                              Positioned(
                                left: 0,
                                right: 0,
                                bottom: 0,
                                child: Container(
                                  color: AppColors.error,
                                  padding: const EdgeInsets.all(2),
                                  child: Text(
                                    l10n.profilePhotoHidden,
                                    textAlign: TextAlign.center,
                                    style: AppTextStyles.caption.copyWith(color: Colors.white),
                                  ),
                                ),
                              ),
                            Positioned(
                              top: 0,
                              right: 0,
                              child: IconButton(
                                key: ValueKey('remove-photo-${photo.id}'),
                                icon: const Icon(Icons.delete_outline),
                                tooltip: l10n.reportRemoveEntry,
                                onPressed: _busy
                                    ? null
                                    : () => _run(() async {
                                          await _api.deleteWorkPhoto(widget.shopId, photo.id);
                                          await _load();
                                        }),
                              ),
                            ),
                          ],
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                    icon: const Icon(Icons.add_a_photo_outlined),
                    label: Text(l10n.profileAddPhoto),
                    onPressed: _busy ? null : _addPhoto,
                  ),
                ],
              ),
            ),
    );
  }
}
