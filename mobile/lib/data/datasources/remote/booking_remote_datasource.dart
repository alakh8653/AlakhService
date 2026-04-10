import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/errors/exceptions.dart';
import '../../models/booking_model.dart';

abstract class BookingRemoteDataSource {
  Future<BookingModel> createBooking({
    required String serviceId,
    required String scheduledAt,
    required String address,
    String? notes,
  });
  Future<List<BookingModel>> getBookings({int page = 1, int limit = 20});
  Future<BookingModel> getBookingById(String id);
  Future<BookingModel> cancelBooking(String id);
  Future<BookingModel> rescheduleBooking(String id, {required String newScheduledAt});
}

class BookingRemoteDataSourceImpl implements BookingRemoteDataSource {
  const BookingRemoteDataSourceImpl({required this.dio});

  final Dio dio;

  @override
  Future<BookingModel> createBooking({
    required String serviceId,
    required String scheduledAt,
    required String address,
    String? notes,
  }) async {
    final response = await dio.post(
      ApiConstants.bookings,
      data: {
        'service_id': serviceId,
        'scheduled_at': scheduledAt,
        'address': address,
        if (notes != null) 'notes': notes,
      },
    );
    _assertSuccess(response);
    return BookingModel.fromJson(response.data as Map<String, dynamic>);
  }

  @override
  Future<List<BookingModel>> getBookings({int page = 1, int limit = 20}) async {
    final response = await dio.get(
      ApiConstants.bookings,
      queryParameters: {'page': page, 'limit': limit},
    );
    _assertSuccess(response);
    final data = response.data['data'] as List<dynamic>;
    return data
        .map((json) => BookingModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<BookingModel> getBookingById(String id) async {
    final response = await dio.get(ApiConstants.bookingById(id));
    _assertSuccess(response);
    return BookingModel.fromJson(response.data as Map<String, dynamic>);
  }

  @override
  Future<BookingModel> cancelBooking(String id) async {
    final response = await dio.patch(ApiConstants.cancelBooking(id));
    _assertSuccess(response);
    return BookingModel.fromJson(response.data as Map<String, dynamic>);
  }

  @override
  Future<BookingModel> rescheduleBooking(
    String id, {
    required String newScheduledAt,
  }) async {
    final response = await dio.patch(
      ApiConstants.rescheduleBooking(id),
      data: {'scheduled_at': newScheduledAt},
    );
    _assertSuccess(response);
    return BookingModel.fromJson(response.data as Map<String, dynamic>);
  }

  void _assertSuccess(Response<dynamic> response) {
    if (response.statusCode == null || response.statusCode! >= 400) {
      throw ServerException(
        message: response.data?['message']?.toString() ?? 'Unknown server error',
        statusCode: response.statusCode,
      );
    }
  }
}
