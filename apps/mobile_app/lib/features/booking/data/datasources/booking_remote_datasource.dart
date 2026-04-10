import '../../../../core/network/api_client.dart';
import '../../../../core/constants/api_constants.dart';
import '../../../../core/errors/exceptions.dart';
import '../models/booking_model.dart';

abstract class BookingRemoteDataSource {
  Future<BookingModel> createBooking({
    required String serviceId,
    required DateTime scheduledAt,
    required String address,
    String? notes,
  });

  Future<List<BookingModel>> getUserBookings({int page = 1});

  Future<BookingModel> getBookingById(String id);

  Future<bool> cancelBooking(String bookingId);
}

class BookingRemoteDataSourceImpl implements BookingRemoteDataSource {
  final ApiClient apiClient;

  BookingRemoteDataSourceImpl({required this.apiClient});

  @override
  Future<BookingModel> createBooking({
    required String serviceId,
    required DateTime scheduledAt,
    required String address,
    String? notes,
  }) async {
    try {
      final response = await apiClient.post(
        ApiConstants.bookings,
        data: {
          'service_id': serviceId,
          'scheduled_at': scheduledAt.toIso8601String(),
          'address': address,
          if (notes != null) 'notes': notes,
        },
      );
      return BookingModel.fromJson(
        response.data['data'] as Map<String, dynamic>,
      );
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }

  @override
  Future<List<BookingModel>> getUserBookings({int page = 1}) async {
    try {
      final response = await apiClient.get(
        ApiConstants.bookings,
        queryParameters: {'page': page},
      );
      final items = response.data['data'] as List<dynamic>;
      return items
          .map((e) => BookingModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }

  @override
  Future<BookingModel> getBookingById(String id) async {
    try {
      final response = await apiClient.get('${ApiConstants.bookings}/$id');
      return BookingModel.fromJson(
        response.data['data'] as Map<String, dynamic>,
      );
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }

  @override
  Future<bool> cancelBooking(String bookingId) async {
    try {
      await apiClient.post(
        ApiConstants.cancelBooking,
        data: {'booking_id': bookingId},
      );
      return true;
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }
}
