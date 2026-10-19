import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../shared/utils/date_utils.dart';
import '../../../shared/widgets/rating_widget.dart';
import '../data/reviews_api.dart';
import 'all_reviews_page.dart';

String reviewsCount(int n) => '$n review${n == 1 ? '' : 's'}';

/// The average, how many reviews, and a bar per star level.
class RatingSummaryView extends StatelessWidget {
  final RatingSummary summary;

  const RatingSummaryView({super.key, required this.summary});

  @override
  Widget build(BuildContext context) {
    final most = summary.distribution.fold<int>(1, (m, d) => d.count > m ? d.count : m);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(summary.average.toStringAsFixed(1), style: AppTextStyles.heading1),
            RatingWidget(rating: summary.average, size: 14),
            const SizedBox(height: 2),
            Text(reviewsCount(summary.count), style: AppTextStyles.caption.themed(context)),
          ],
        ),
        const SizedBox(width: 20),
        Expanded(
          child: Column(
            children: [
              for (final stars in [5, 4, 3, 2, 1])
                Semantics(
                  label: '$stars star${stars == 1 ? '' : 's'}: ${reviewsCount(summary.countFor(stars))}',
                  excludeSemantics: true,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      children: [
                        SizedBox(width: 14, child: Text('$stars', style: AppTextStyles.caption.themed(context))),
                        const Icon(Icons.star, size: 12, color: AppColors.starFilled),
                        const SizedBox(width: 6),
                        Expanded(
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(4),
                            child: LinearProgressIndicator(
                              value: summary.countFor(stars) / most,
                              minHeight: 6,
                              backgroundColor: context.colors.outlineVariant,
                              valueColor: const AlwaysStoppedAnimation(AppColors.starFilled),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

/// One review, with the shop's reply under it.
class ReviewTile extends StatelessWidget {
  final Review review;

  const ReviewTile({super.key, required this.review});

  @override
  Widget build(BuildContext context) {
    final reply = review.reply;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(review.reviewerName, style: AppTextStyles.subtitle2.themed(context))),
              Text(AppDateUtils.formatDate(review.createdAt), style: AppTextStyles.caption.themed(context)),
            ],
          ),
          const SizedBox(height: 2),
          Row(
            children: [
              RatingWidget(rating: review.rating.toDouble(), size: 14),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  'Verified booking',
                  style: AppTextStyles.caption.copyWith(color: context.palette.success),
                ),
              ),
            ],
          ),
          if (review.comment != null && review.comment!.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(review.comment!, style: AppTextStyles.body2.themed(context)),
          ],
          if (reply != null)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: context.colors.primaryContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Reply from the shop · ${AppDateUtils.formatDate(reply.updatedAt)}',
                    style: AppTextStyles.caption.themed(context).copyWith(fontWeight: FontWeight.w600, color: context.colors.onPrimaryContainer),
                  ),
                  const SizedBox(height: 4),
                  Text(reply.text, style: AppTextStyles.body2.themed(context)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// The reviews part of a service's page: the summary, a few recent reviews and a way to all of them.
class ReviewsSection extends StatefulWidget {
  final String shopId;
  final String? shopName;
  final ReviewsApi api;

  /// The shop's summary, once the page has it.
  final RatingSummary? summary;

  const ReviewsSection({super.key, required this.shopId, required this.api, this.summary, this.shopName});

  @override
  State<ReviewsSection> createState() => _ReviewsSectionState();
}

class _ReviewsSectionState extends State<ReviewsSection> {
  static const _recent = 3;
  List<Review>? _reviews;

  @override
  void initState() {
    super.initState();
    widget.api.reviews(widget.shopId, limit: _recent).then((page) {
      if (mounted) setState(() => _reviews = page.items);
    }).catchError((Object _) {
      if (mounted) setState(() => _reviews = const []);
    });
  }

  @override
  Widget build(BuildContext context) {
    final summary = widget.summary;
    if (summary == null) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(header: true, child: const Text('Ratings & reviews', style: AppTextStyles.subtitle1)),
        const SizedBox(height: 8),
        if (summary.count == 0)
          Text(
            'No reviews yet. Customers can review the shop after a completed booking.',
            style: AppTextStyles.body2.themed(context),
          )
        else ...[
          RatingSummaryView(summary: summary),
          const SizedBox(height: 4),
          for (final r in _reviews ?? const <Review>[]) ...[
            const Divider(height: 1),
            ReviewTile(review: r),
          ],
          // Always offered: the full list also filters by stars.
          Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => AllReviewsPage(shopId: widget.shopId, api: widget.api, shopName: widget.shopName),
                  ),
                ),
                child: Text('See all reviews (${summary.count})'),
              ),
            ),
        ],
      ],
    );
  }
}
