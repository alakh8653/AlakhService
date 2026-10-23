import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../l10n/l10n.dart';

/// Category tile shown in the home services grid.
class ServiceCategoryCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  const ServiceCategoryCard({
    super.key,
    required this.icon,
    required this.label,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: context.colors.primaryContainer,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(icon, color: context.colors.primary, size: 28),
            ),
            const SizedBox(height: 6),
            // Two lines, so "Beauty Parlour" and "Laptop & Phone" aren't cut to "Beauty Parl…".
            Text(
              label,
              style: AppTextStyles.caption.copyWith(color: context.colors.onSurface),
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}

/// Promotional banner shown at the top of the home screen when there is no booking coming up.
class BannerWidget extends StatelessWidget {
  final VoidCallback? onTap;

  const BannerWidget({super.key, this.onTap});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: context.l10n.bannerSemantics,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          constraints: const BoxConstraints(minHeight: 140),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppColors.primary, AppColors.primaryDark],
            ),
            borderRadius: BorderRadius.circular(20),
          ),
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      context.l10n.bannerTrack,
                      style: AppTextStyles.heading3.copyWith(
                        color: AppColors.textLight,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: AppColors.textLight,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        context.l10n.bannerMyBookings,
                        style: AppTextStyles.subtitle2.copyWith(color: AppColors.primary),
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(
                Icons.home_repair_service,
                size: 80,
                color: Colors.white24,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The customer's next booking, at the top of the home screen.
class NextBookingCard extends StatelessWidget {
  final String serviceName;
  final String when;
  final String status;
  final VoidCallback onTap;

  const NextBookingCard({
    super.key,
    required this.serviceName,
    required this.when,
    required this.status,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Semantics(
        button: true,
        label: context.l10n.nextBookingSemantics(serviceName, when, status),
        excludeSemantics: true,
        child: Material(
          borderRadius: BorderRadius.circular(20),
          clipBehavior: Clip.antiAlias,
          child: Ink(
            decoration: const BoxDecoration(
              gradient: LinearGradient(colors: [AppColors.primary, AppColors.primaryDark]),
            ),
            child: InkWell(
              onTap: onTap,
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(context.l10n.nextBooking, style: AppTextStyles.caption.copyWith(color: AppColors.textLight)),
                          const SizedBox(height: 4),
                          Text(serviceName, style: AppTextStyles.heading3.copyWith(color: AppColors.textLight)),
                          const SizedBox(height: 2),
                          Text(when, style: AppTextStyles.body2.copyWith(color: AppColors.textLight)),
                          const SizedBox(height: 10),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppColors.textLight,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              status,
                              style: AppTextStyles.caption.copyWith(color: AppColors.primaryDark, fontWeight: FontWeight.w600),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(Icons.chevron_right, color: AppColors.textLight),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Search bar used at the top of list pages.
class SearchBarWidget extends StatelessWidget {
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final String? hint;

  const SearchBarWidget({
    super.key,
    this.onChanged,
    this.onSubmitted,
    this.hint,
  });

  @override
  Widget build(BuildContext context) {
    // A plain field in the app's input style; the theme's own border used to draw a second box
    // inside a bordered container.
    return TextField(
      onChanged: onChanged,
      onSubmitted: (q) {
        if (q.trim().isNotEmpty) onSubmitted?.call(q.trim());
      },
      textInputAction: TextInputAction.search,
      decoration: InputDecoration(
        hintText: hint ?? context.l10n.searchServicesHint,
        hintStyle: AppTextStyles.body2.themed(context),
        prefixIcon: Icon(Icons.search, color: context.palette.muted),
        contentPadding: const EdgeInsets.symmetric(vertical: 12),
      ),
    );
  }
}
