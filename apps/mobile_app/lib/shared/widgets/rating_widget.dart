import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/app_text_styles.dart';
import '../../l10n/l10n.dart';

/// "4.6 out of 5 stars": what a screen reader says for a row of stars.
String starsLabel(num rating, {AppLocalizations? l10n}) => (l10n ?? englishL10n)
    .starsLabel(rating == rating.roundToDouble() ? '${rating.round()}' : rating.toStringAsFixed(1));

/// "★ 4.6 (128)", or "New" when nobody has rated it yet, read out in words.
class RatingBadge extends StatelessWidget {
  final double rating;
  final int count;
  final TextStyle? style;

  const RatingBadge({super.key, required this.rating, required this.count, this.style});

  @override
  Widget build(BuildContext context) {
    final textStyle = style ?? AppTextStyles.caption.themed(context);
    if (count == 0) {
      return Semantics(
        label: context.l10n.ratingNewSemantics,
        excludeSemantics: true,
        child: Text(context.l10n.ratingNew, style: textStyle.copyWith(color: context.palette.success)),
      );
    }
    return Semantics(
      label: context.l10n.ratedSemantics(rating.toStringAsFixed(1), count),
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.star, size: 14, color: AppColors.starFilled),
          const SizedBox(width: 2),
          Flexible(child: Text('${rating.toStringAsFixed(1)} ($count)', style: textStyle)),
        ],
      ),
    );
  }
}

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
    return Semantics(
      label: starsLabel(rating, l10n: context.l10n),
      excludeSemantics: true,
      child: Row(
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
              style: AppTextStyles.caption.themed(context).copyWith(
                color: context.palette.muted,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
