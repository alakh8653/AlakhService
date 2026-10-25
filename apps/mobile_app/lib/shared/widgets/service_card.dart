import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/app_text_styles.dart';
import '../../features/services/domain/entities/service_entity.dart';
import '../utils/format.dart';
import 'rating_widget.dart';
import '../../l10n/l10n.dart';

/// "At shop · Home visit · Pickup & drop": how a service can be had, for cards and details.
String serviceModesLabel(List<String> modes, {AppLocalizations? l10n}) {
  final l = l10n ?? englishL10n;
  return [
    for (final m in modes)
      switch (m) {
        ServiceMode.atHome => l.modeHomeVisit,
        ServiceMode.pickupDrop => l.modePickupDrop,
        _ => l.modeAtShop,
      },
  ].join(' · ');
}

class ServiceCard extends StatelessWidget {
  final ServiceEntity service;
  final VoidCallback? onTap;

  const ServiceCard({super.key, required this.service, this.onTap});

  Widget _placeholder(BuildContext context) => Container(
        width: 96,
        color: context.colors.primaryContainer,
        child: Icon(Icons.home_repair_service, color: context.colors.primary, size: 36),
      );

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    // The catalogue's generic "Service" category says nothing, so the card shows how it's offered.
    final subtitle = [
      if (service.category.isNotEmpty && service.category != 'Service') service.category,
      if (service.durationMinutes != null && service.durationMinutes! > 0) l10n.minutesShort(service.durationMinutes!),
    ].join(' · ');
    return Semantics(
      button: true,
      child: Material(
        color: context.colors.surface,
        borderRadius: BorderRadius.circular(16),
        elevation: 1,
        shadowColor: AppColors.shadow,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: 100),
                  child: service.imageUrl != null
                      ? Image.network(
                          service.imageUrl!,
                          width: 96,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => _placeholder(context),
                        )
                      : _placeholder(context),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: Text(
                                service.name,
                                style: AppTextStyles.subtitle1,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            if (!service.isAvailable)
                              Container(
                                margin: const EdgeInsets.only(left: 6),
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: context.colors.error.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  l10n.unavailable,
                                  style: AppTextStyles.caption.copyWith(color: context.colors.error),
                                ),
                              ),
                          ],
                        ),
                        if (subtitle.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(subtitle, style: AppTextStyles.caption.themed(context)),
                        ],
                        const SizedBox(height: 4),
                        Text(
                          serviceModesLabel(service.serviceModes, l10n: l10n),
                          style: AppTextStyles.caption.copyWith(color: context.colors.onPrimaryContainer),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            Expanded(
                              child: Align(
                                alignment: AlignmentDirectional.centerStart,
                                child: RatingBadge(rating: service.rating, count: service.reviewCount),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              rupees(service.basePrice),
                              style: AppTextStyles.subtitle1.copyWith(color: context.colors.primary),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
