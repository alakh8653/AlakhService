import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/rating_widget.dart';
import '../../domain/entities/service_entity.dart';

class ServiceDetailPage extends StatelessWidget {
  final ServiceEntity service;

  const ServiceDetailPage({super.key, required this.service});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 240,
            pinned: true,
            flexibleSpace: FlexibleSpaceBar(
              title: Text(service.name),
              background: service.imageUrl != null
                  ? Image.network(service.imageUrl!, fit: BoxFit.cover)
                  : Container(
                      color: AppColors.primaryLight,
                      child: const Icon(
                        Icons.home_repair_service,
                        size: 80,
                        color: AppColors.primary,
                      ),
                    ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(service.name, style: AppTextStyles.heading2),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.accentLight,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          service.category,
                          style: AppTextStyles.caption
                              .copyWith(color: AppColors.accent),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      RatingWidget(rating: service.rating),
                      const SizedBox(width: 8),
                      Text(
                        '(${service.reviewCount} reviews)',
                        style: AppTextStyles.caption,
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text('About this service', style: AppTextStyles.subtitle1),
                  const SizedBox(height: 8),
                  Text(service.description, style: AppTextStyles.body2),
                  if (service.tags.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      children: service.tags
                          .map(
                            (t) => Chip(
                              label: Text(t, style: AppTextStyles.caption),
                              backgroundColor: AppColors.primaryLight,
                            ),
                          )
                          .toList(),
                    ),
                  ],
                  const SizedBox(height: 24),
                  Row(
                    children: [
                      Text('Starting at', style: AppTextStyles.body2),
                      const SizedBox(width: 8),
                      Text(
                        '₹${service.basePrice.toStringAsFixed(0)}',
                        style: AppTextStyles.heading3
                            .copyWith(color: AppColors.primary),
                      ),
                      Text(
                        ' / ${service.priceUnit}',
                        style: AppTextStyles.body2,
                      ),
                    ],
                  ),
                  const SizedBox(height: 32),
                  CustomButton(
                    label: 'Book Now',
                    onPressed: () {
                      // Navigate to booking flow
                    },
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
