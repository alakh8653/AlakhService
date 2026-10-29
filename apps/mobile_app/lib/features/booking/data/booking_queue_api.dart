import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// Where a booking stands in today's queue at its shop (booking_service's GET /bookings/{id}/queue).
class BookingQueue {
  final String bookingId;

  /// WAITING, YOUR_TURN, IN_PROGRESS, CHECK_IN_NEEDED (late: check in to rejoin), UNSERVABLE (cannot be
  /// fitted in today), or NOT_TODAY / NOT_QUEUED (no live queue for it).
  final String state;
  final int? position;
  final int? peopleAhead;
  final int? beingServed;
  final DateTime? estimatedStart;

  /// The likely range of the start.
  final DateTime? etaMin;
  final DateTime? etaMax;
  final int? waitMinutes;
  final int? runningLateMinutes;

  /// Who is expected to serve them.
  final String? staffName;

  /// PREFERRED_UNAVAILABLE: their chosen professional is away today.
  final String? reason;
  final bool checkedIn;
  final bool canCheckIn;

  const BookingQueue({
    this.bookingId = '',
    required this.state,
    this.position,
    this.peopleAhead,
    this.beingServed,
    this.estimatedStart,
    this.etaMin,
    this.etaMax,
    this.waitMinutes,
    this.runningLateMinutes,
    this.staffName,
    this.reason,
    this.checkedIn = false,
    this.canCheckIn = false,
  });

  /// In today's queue: there is something live to show.
  bool get isLive => const {'WAITING', 'YOUR_TURN', 'IN_PROGRESS', 'CHECK_IN_NEEDED', 'UNSERVABLE'}.contains(state);

  static DateTime? _time(Object? value) => DateTime.tryParse((value as String?) ?? '')?.toLocal();

  factory BookingQueue.fromJson(Map<String, dynamic> json) => BookingQueue(
        bookingId: json['booking_id'] as String? ?? '',
        state: json['state'] as String,
        position: (json['position'] as num?)?.toInt(),
        peopleAhead: (json['people_ahead'] as num?)?.toInt(),
        beingServed: (json['being_served'] as num?)?.toInt(),
        estimatedStart: _time(json['estimated_start']),
        etaMin: _time(json['eta_min']),
        etaMax: _time(json['eta_max']),
        waitMinutes: (json['wait_minutes'] as num?)?.toInt(),
        runningLateMinutes: (json['running_late_minutes'] as num?)?.toInt(),
        staffName: json['staff_name'] as String?,
        reason: json['reason'] as String?,
        checkedIn: json['checked_in'] as bool? ?? false,
        canCheckIn: json['can_check_in'] as bool? ?? false,
      );
}

class BookingQueueApi {
  final ApiClient apiClient;

  BookingQueueApi(this.apiClient);

  Future<BookingQueue> forBooking(String bookingId) => _call(() => apiClient.get(ApiConstants.bookingQueue(bookingId)));

  /// Tells the shop the customer has arrived.
  Future<BookingQueue> checkIn(String bookingId) => _call(() => apiClient.post(ApiConstants.bookingCheckIn(bookingId)));

  /// Joins the shop's line for [serviceId] now, without a booked time.
  Future<BookingQueue> joinLine(String serviceId, {String? preferredStaffId}) => _call(
        () => apiClient.post(ApiConstants.joinLine, data: {
          'service_id': serviceId,
          if (preferredStaffId != null) 'preferred_staff_id': preferredStaffId,
        }),
      );

  Future<BookingQueue> _call(Future<Response<dynamic>> Function() request) async {
    try {
      final response = await request();
      return BookingQueue.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
