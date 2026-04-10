import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text_styles.dart';

class RatingWidget extends StatelessWidget {
  final double rating;
  final int maxStars;
  final double size;
  final bool showValue;

  const RatingWidget({
    super.key,
    required this.rating,
    this.maxStars = 5,
    this.size = 16,
    this.showValue = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        ...List.generate(maxStars, (i) {
          final filled = i < rating.floor();
          final partial = !filled && i < rating;
          return Icon(
            partial ? Icons.star_half : Icons.star,
            size: size,
            color: filled || partial ? AppColors.starFilled : AppColors.starEmpty,
          );
        }),
        if (showValue) ...[
          const SizedBox(width: 4),
          Text(
            rating.toStringAsFixed(1),
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ],
    );
  }
}
