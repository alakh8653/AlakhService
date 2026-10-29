import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// Where a booking stands in today's queue at its shop (booking_service's GET /bookings/{id}/queue).
class BookingQueue {
  /// WAITING, YOUR_TURN, IN_PROGRESS, or NOT_TODAY / NOT_QUEUED (no live queue for it).
  final String state;
  final int? position;
  final int? peopleAhead;
  final int? beingServed;
  final DateTime? estimatedStart;
  final int? waitMinutes;
  final int? runningLateMinutes;

  const BookingQueue({
    required this.state,
    this.position,
    this.peopleAhead,
    this.beingServed,
    this.estimatedStart,
    this.waitMinutes,
    this.runningLateMinutes,
  });

  /// In today's queue: there is something live to show.
  bool get isLive => const {'WAITING', 'YOUR_TURN', 'IN_PROGRESS'}.contains(state);

  factory BookingQueue.fromJson(Map<String, dynamic> json) => BookingQueue(
        state: json['state'] as String,
        position: (json['position'] as num?)?.toInt(),
        peopleAhead: (json['people_ahead'] as num?)?.toInt(),
        beingServed: (json['being_served'] as num?)?.toInt(),
        estimatedStart: DateTime.tryParse((json['estimated_start'] as String?) ?? '')?.toLocal(),
        waitMinutes: (json['wait_minutes'] as num?)?.toInt(),
        runningLateMinutes: (json['running_late_minutes'] as num?)?.toInt(),
      );
}

class BookingQueueApi {
  final ApiClient apiClient;

  BookingQueueApi(this.apiClient);

  Future<BookingQueue> forBooking(String bookingId) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.bookingQueue(bookingId));
      return BookingQueue.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
