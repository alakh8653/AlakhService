import 'package:flutter/material.dart';

import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../data/shop_profile_api.dart';

/// A business's experience, languages and photos of its work. Shows nothing until it has something to show, and
/// a profile that fails to load never gets in the way of booking.
class ShopProfileSection extends StatefulWidget {
  final String shopId;
  final ShopProfileApi api;

  const ShopProfileSection({super.key, required this.shopId, required this.api});

  @override
  State<ShopProfileSection> createState() => _ShopProfileSectionState();
}

class _ShopProfileSectionState extends State<ShopProfileSection> {
  ShopProfile? _profile;

  @override
  void initState() {
    super.initState();
    widget.api.profile(widget.shopId).then((profile) {
      if (mounted) setState(() => _profile = profile);
    }).catchError((Object _) {});
  }

  void _open(WorkPhoto photo) {
    Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: photo.caption == null ? null : Text(photo.caption!)),
          backgroundColor: Colors.black,
          body: Center(child: InteractiveViewer(child: Image.network(photo.url, errorBuilder: _missing))),
        ),
      ),
    );
  }

  static Widget _missing(BuildContext context, Object error, StackTrace? stack) => const SizedBox(
        width: 120,
        height: 120,
        child: Center(child: Icon(Icons.image_not_supported_outlined)),
      );

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final profile = _profile;
    if (profile == null || profile.isEmpty) return const SizedBox.shrink();
    final years = profile.yearsExperience;
    return Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.profileAboutTitle, style: AppTextStyles.heading3),
          if (years != null && years > 0) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                Icon(Icons.workspace_premium_outlined, size: 18, color: context.palette.muted),
                const SizedBox(width: 6),
                Expanded(child: Text(l10n.profileYears(years), style: AppTextStyles.body2.themed(context))),
              ],
            ),
          ],
          if (profile.languages.isNotEmpty) ...[
            const SizedBox(height: 6),
            Row(
              children: [
                Icon(Icons.translate, size: 18, color: context.palette.muted),
                const SizedBox(width: 6),
                Expanded(child: Text(profile.languages.join(', '), style: AppTextStyles.body2.themed(context))),
              ],
            ),
          ],
          if ((profile.about ?? '').isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(profile.about!, style: AppTextStyles.body2.themed(context)),
          ],
          if (profile.photos.isNotEmpty) ...[
            const SizedBox(height: 12),
            SizedBox(
              height: 120,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: profile.photos.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (context, i) {
                  final photo = profile.photos[i];
                  return InkWell(
                    key: ValueKey('work-photo-${photo.id}'),
                    onTap: () => _open(photo),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.network(
                        photo.url,
                        width: 120,
                        height: 120,
                        fit: BoxFit.cover,
                        cacheWidth: 360,
                        semanticLabel: photo.caption,
                        errorBuilder: _missing,
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ],
      ),
    );
  }
}
