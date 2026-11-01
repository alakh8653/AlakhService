import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// One change to the customer's points (payment_service): EARN, REDEEM, REDEEM_RETURN, REFERRAL_BONUS, CLAWBACK.
class PointsEntry {
  final String kind;
  final int points;
  final String? note;
  final DateTime createdAt;

  const PointsEntry({required this.kind, required this.points, this.note, required this.createdAt});

  factory PointsEntry.fromJson(Map<String, dynamic> json) => PointsEntry(
        kind: json['kind'] as String,
        points: (json['points'] as num).toInt(),
        note: json['note'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
      );
}

/// The customer's points, what they are worth and the rules, and their referral code.
class LoyaltySummary {
  final int points;
  final int valueCents;
  final int pointValueCents;
  final int pointsPer100Rupees;
  final int redeemMaxPercent;
  final String referralCode;
  final int referralBonusPoints;
  final int friendsRewarded;
  final int friendsPending;
  final bool referredByFriend;
  final List<PointsEntry> history;

  const LoyaltySummary({
    required this.points,
    required this.valueCents,
    this.pointValueCents = 100,
    this.pointsPer100Rupees = 2,
    this.redeemMaxPercent = 20,
    required this.referralCode,
    this.referralBonusPoints = 100,
    this.friendsRewarded = 0,
    this.friendsPending = 0,
    this.referredByFriend = false,
    this.history = const [],
  });

  /// What the points take off a booking costing [price] rupees (they pay up to [redeemMaxPercent] of it).
  double discountOn(double price) {
    final capCents = (price * 100).round() * redeemMaxPercent ~/ 100 ~/ pointValueCents * pointValueCents;
    return (valueCents < capCents ? valueCents : capCents) / 100;
  }

  factory LoyaltySummary.fromJson(Map<String, dynamic> json) => LoyaltySummary(
        points: (json['points'] as num).toInt(),
        valueCents: (json['value_cents'] as num).toInt(),
        pointValueCents: (json['point_value_cents'] as num?)?.toInt() ?? 100,
        pointsPer100Rupees: (json['points_per_100_rupees'] as num?)?.toInt() ?? 2,
        redeemMaxPercent: (json['redeem_max_percent'] as num?)?.toInt() ?? 20,
        referralCode: json['referral_code'] as String,
        referralBonusPoints: (json['referral_bonus_points'] as num?)?.toInt() ?? 100,
        friendsRewarded: (json['friends_rewarded'] as num?)?.toInt() ?? 0,
        friendsPending: (json['friends_pending'] as num?)?.toInt() ?? 0,
        referredByFriend: (json['referred_by_friend'] as bool?) ?? false,
        history: [for (final e in (json['history'] as List? ?? const [])) PointsEntry.fromJson(e as Map<String, dynamic>)],
      );
}

/// Loyalty points and referrals (payment_service).
class LoyaltyApi {
  final ApiClient apiClient;

  LoyaltyApi(this.apiClient);

  Future<LoyaltySummary> summary() async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.loyalty);
      return LoyaltySummary.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// Uses a friend's referral code; the server's message says what both of them get.
  Future<String> useReferralCode(String code) async {
    try {
      final response = await apiClient.post<Map<String, dynamic>>(ApiConstants.referral, data: {'code': code.trim()});
      return (response.data?['message'] as String?) ?? '';
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
