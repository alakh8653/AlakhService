import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text_styles.dart';
import '../../features/services/domain/entities/service_entity.dart';
import '../utils/format.dart';
import 'rating_widget.dart';

/// "At shop · Home visit · Pickup & drop": how a service can be had, for cards and details.
String serviceModesLabel(List<String> modes) => [
      for (final m in modes)
        switch (m) {
          ServiceMode.atHome => 'Home visit',
          ServiceMode.pickupDrop => 'Pickup & drop',
          _ => 'At shop',
        },
    ].join(' · ');

class ServiceCard extends StatelessWidget {
  final ServiceEntity service;
  final VoidCallback? onTap;

  const ServiceCard({super.key, required this.service, this.onTap});

  Widget _placeholder() => Container(
        width: 96,
        color: AppColors.primaryLight,
        child: const Icon(Icons.home_repair_service, color: AppColors.primary, size: 36),
      );

  @override
  Widget build(BuildContext context) {
    // The catalogue's generic "Service" category says nothing, so the card shows how it's offered.
    final subtitle = [
      if (service.category.isNotEmpty && service.category != 'Service') service.category,
      if (service.durationMinutes != null && service.durationMinutes! > 0) '${service.durationMinutes} min',
    ].join(' · ');
    return Semantics(
      button: true,
      child: Material(
        color: AppColors.surface,
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
                          errorBuilder: (_, __, ___) => _placeholder(),
                        )
                      : _placeholder(),
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
                                  color: AppColors.error.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  'Unavailable',
                                  style: AppTextStyles.caption.copyWith(color: AppColors.error),
                                ),
                              ),
                          ],
                        ),
                        if (subtitle.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(subtitle, style: AppTextStyles.caption),
                        ],
                        const SizedBox(height: 4),
                        Text(
                          serviceModesLabel(service.serviceModes),
                          style: AppTextStyles.caption.copyWith(color: AppColors.primaryDark),
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
                              style: AppTextStyles.subtitle1.copyWith(color: AppColors.primary),
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
