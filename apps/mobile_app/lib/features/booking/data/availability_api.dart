import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// Why a day has the times it has (booking_service's GET /availability `status`).
class DayStatus {
  DayStatus._();

  static const available = 'AVAILABLE';
  static const closed = 'CLOSED';
  static const holiday = 'HOLIDAY';
  static const fullyBooked = 'FULLY_BOOKED';
  static const noMoreToday = 'NO_MORE_TODAY';

  /// The shop hasn't published opening hours: any future time can be requested.
  static const notConfigured = 'NOT_CONFIGURED';
}

/// A start time the shop can take.
class AvailableSlot {
  /// The instant to book (UTC), exactly as the server listed it.
  final DateTime at;

  /// Shop-local hour and minute ("10:30"), shown as is wherever the phone is.
  final int hour, minute;

  const AvailableSlot({required this.at, required this.hour, required this.minute});
}

class DayAvailability {
  final bool hoursConfigured;
  final String status;
  final String? message;
  final String? holidayNote;
  final List<AvailableSlot> slots;

  const DayAvailability({
    required this.hoursConfigured,
    required this.status,
    this.message,
    this.holidayNote,
    this.slots = const [],
  });

  factory DayAvailability.fromJson(Map<String, dynamic> json) => DayAvailability(
        hoursConfigured: json['hours_configured'] as bool,
        status: json['status'] as String,
        message: json['message'] as String?,
        holidayNote: json['holiday_note'] as String?,
        slots: [
          for (final s in (json['slots'] as List? ?? const []).cast<Map<String, dynamic>>())
            AvailableSlot(
              at: DateTime.parse(s['start'] as String).toUtc(),
              hour: int.parse((s['time'] as String).split(':')[0]),
              minute: int.parse((s['time'] as String).split(':')[1]),
            ),
        ],
      );
}

/// Bookable times of a service on a day, from the shop's opening hours, holidays and bookings (booking_service).
class AvailabilityApi {
  final ApiClient apiClient;

  AvailabilityApi(this.apiClient);

  /// [day] is a calendar day in the shop's time zone (India); only its date is used.
  Future<DayAvailability> forDay(String serviceId, DateTime day) async {
    final date = '${day.year.toString().padLeft(4, '0')}-${day.month.toString().padLeft(2, '0')}-'
        '${day.day.toString().padLeft(2, '0')}';
    try {
      final response = await apiClient.get<Map<String, dynamic>>(
        ApiConstants.availability,
        queryParameters: {'service_id': serviceId, 'date': date},
      );
      return DayAvailability.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
