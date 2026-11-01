import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// When the professional reaches the customer's door for a home visit (GET /bookings/{id}/arrival).
class HomeArrival {
  /// PLANNED, ON_THE_WAY, ARRIVED; or NOT_HOME_VISIT, NOT_ASSIGNED, NOT_TODAY, DONE (nothing live).
  final String state;
  final DateTime? arriveAt;
  final DateTime? arriveMin;
  final DateTime? arriveMax;
  final int? jobsBefore;
  final int lateMinutes;

  const HomeArrival({required this.state, this.arriveAt, this.arriveMin, this.arriveMax, this.jobsBefore, this.lateMinutes = 0});

  bool get isLive => const {'PLANNED', 'ON_THE_WAY', 'ARRIVED'}.contains(state);

  static DateTime? _time(Object? v) => DateTime.tryParse((v as String?) ?? '')?.toLocal();

  factory HomeArrival.fromJson(Map<String, dynamic> j) => HomeArrival(
        state: j['state'] as String,
        arriveAt: _time(j['arrive_at']),
        arriveMin: _time(j['arrive_min']),
        arriveMax: _time(j['arrive_max']),
        jobsBefore: (j['jobs_before'] as num?)?.toInt(),
        lateMinutes: (j['late_minutes'] as num?)?.toInt() ?? 0,
      );
}

/// One stop on a professional's route today (GET /bookings/assigned/route).
class RouteStop {
  final String bookingId;
  final DateTime leaveAt;
  final DateTime arriveAt;
  final int travelMinutes;
  final int lateMinutes;

  const RouteStop({required this.bookingId, required this.leaveAt, required this.arriveAt, required this.travelMinutes, this.lateMinutes = 0});

  factory RouteStop.fromJson(Map<String, dynamic> j) => RouteStop(
        bookingId: j['booking_id'] as String,
        leaveAt: DateTime.parse(j['leave_at'] as String).toLocal(),
        arriveAt: DateTime.parse(j['arrive_at'] as String).toLocal(),
        travelMinutes: (j['travel_minutes'] as num).toInt(),
        lateMinutes: (j['late_minutes'] as num?)?.toInt() ?? 0,
      );
}

class HomeArrivalApi {
  final ApiClient apiClient;

  HomeArrivalApi(this.apiClient);

  Future<HomeArrival> forBooking(String bookingId) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.bookingArrival(bookingId));
      return HomeArrival.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// The signed-in professional's home visits today, by booking id.
  Future<Map<String, RouteStop>> myRoute() async {
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.myRoute);
      return {
        for (final s in response.data!.cast<Map<String, dynamic>>()) s['booking_id'] as String: RouteStop.fromJson(s),
      };
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
