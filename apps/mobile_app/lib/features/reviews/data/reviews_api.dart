import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// A shop's average and how many ratings it has: "★ 4.6 (128)".
class ShopRating {
  final double average;
  final int count;

  const ShopRating({required this.average, required this.count});
}

class RatingSummary {
  final double average;
  final int count;

  /// Ratings per star level, 5 stars first.
  final List<({int stars, int count})> distribution;

  const RatingSummary({required this.average, required this.count, required this.distribution});

  factory RatingSummary.fromJson(Map<String, dynamic> json) => RatingSummary(
        average: (json['average_rating'] as num).toDouble(),
        count: json['review_count'] as int,
        distribution: [
          for (final d in (json['distribution'] as List? ?? const []).cast<Map<String, dynamic>>())
            (stars: d['stars'] as int, count: d['count'] as int),
        ],
      );

  /// How many ratings gave [stars].
  int countFor(int stars) => distribution.where((d) => d.stars == stars).fold(0, (sum, d) => sum + d.count);
}

class OwnerReply {
  final String text;
  final DateTime updatedAt;

  const OwnerReply({required this.text, required this.updatedAt});
}

class Review {
  final String id;
  final String? serviceId;
  final int rating;
  final String? comment;

  /// First name and last initial ("Priya S."); never the full name.
  final String reviewerName;
  final DateTime createdAt;
  final OwnerReply? reply;

  const Review({
    required this.id,
    required this.rating,
    required this.reviewerName,
    required this.createdAt,
    this.serviceId,
    this.comment,
    this.reply,
  });

  factory Review.fromJson(Map<String, dynamic> json) {
    final reply = json['reply'] as Map<String, dynamic>?;
    return Review(
      id: json['id'] as String,
      serviceId: json['service_id'] as String?,
      rating: (json['rating'] as num).round(),
      comment: json['comment'] as String?,
      reviewerName: (json['reviewer_name'] as String?) ?? 'Verified customer',
      createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
      reply: reply == null
          ? null
          : OwnerReply(
              text: reply['text'] as String,
              updatedAt: DateTime.parse((reply['updated_at'] ?? reply['created_at']) as String).toLocal(),
            ),
    );
  }
}

class ReviewPage {
  final List<Review> items;
  final int total;

  const ReviewPage({required this.items, required this.total});
}

/// Reviews customers read when choosing a shop (shop_service; public, no sign-in needed).
class ReviewsApi {
  final ApiClient apiClient;

  ReviewsApi(this.apiClient);

  Future<RatingSummary> summary(String shopId) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.reviewSummary(shopId));
      return RatingSummary.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// Newest first; [rating] keeps only reviews with that many stars.
  Future<ReviewPage> reviews(String shopId, {int skip = 0, int limit = 10, int? rating}) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(
        ApiConstants.shopReviews(shopId),
        queryParameters: {'skip': skip, 'limit': limit, if (rating != null) 'rating': rating},
      );
      final data = response.data!;
      return ReviewPage(
        items: [for (final r in (data['items'] as List).cast<Map<String, dynamic>>()) Review.fromJson(r)],
        total: data['total'] as int,
      );
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// The rating of each shop in [shopIds], in one request (shops without a row are left out).
  Future<Map<String, ShopRating>> ratings(Iterable<String> shopIds) async {
    final ids = shopIds.toSet().take(50).toList();
    if (ids.isEmpty) return const {};
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.shopRatings, queryParameters: {'ids': ids.join(',')});
      return {
        for (final r in response.data!.cast<Map<String, dynamic>>())
          r['shop_id'] as String: ShopRating(
            average: (r['average_rating'] as num).toDouble(),
            count: r['review_count'] as int,
          ),
      };
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
