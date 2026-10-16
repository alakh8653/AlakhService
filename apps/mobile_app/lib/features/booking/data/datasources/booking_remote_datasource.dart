import 'package:dio/dio.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_errors.dart';
import '../../../services/data/datasources/service_remote_datasource.dart';
import '../../domain/entities/booking.dart';
import '../models/booking_model.dart';

abstract class BookingRemoteDataSource {
  Future<BookingModel> createBooking({
    required String serviceId,
    required DateTime scheduledAt,
    required String address,
    String? notes,
    String? couponCode,
    BookingDelivery delivery = BookingDelivery.atShop,
  });

  Future<List<BookingModel>> getUserBookings({int page = 1});

  Future<BookingModel> getBookingById(String id);

  Future<bool> cancelBooking(String bookingId, {String reason});
}

/// The signed-in customer's bookings in booking_service. The price, shop and duration of a new
/// booking are set by the server from the catalogue.
class BookingRemoteDataSourceImpl implements BookingRemoteDataSource {
  final ApiClient apiClient;
  final ServiceRemoteDataSource? services;
  final Map<String, String> _serviceNames = {};

  BookingRemoteDataSourceImpl({required this.apiClient, this.services});

  Future<String?> _serviceName(String serviceId) async {
    if (_serviceNames.containsKey(serviceId)) return _serviceNames[serviceId];
    try {
      final service = await services?.getServiceById(serviceId);
      if (service != null) _serviceNames[serviceId] = service.name;
      return service?.name;
    } catch (_) {
      return null; // a missing name is cosmetic; the booking still shows
    }
  }

  Future<BookingModel> _model(Map<String, dynamic> json) async =>
      BookingModel.fromJson(json, serviceName: await _serviceName(json['service_id'] as String));

  @override
  Future<BookingModel> createBooking({
    required String serviceId,
    required DateTime scheduledAt,
    required String address,
    String? notes,
    String? couponCode,
    BookingDelivery delivery = BookingDelivery.atShop,
  }) async {
    try {
      final response = await apiClient.post<Map<String, dynamic>>(
        ApiConstants.bookings,
        data: {
          'service_id': serviceId,
          'scheduled_at': scheduledAt.toUtc().toIso8601String(),
          'notes': BookingModel.composeNotes(address, notes),
          if (couponCode != null && couponCode.trim().isNotEmpty) 'coupon_code': couponCode.trim(),
          'service_mode': delivery.mode,
          if (delivery.addressId != null) 'address_id': delivery.addressId,
          if (delivery.itemDescription != null && delivery.itemDescription!.trim().isNotEmpty)
            'item_description': delivery.itemDescription!.trim(),
        },
      );
      return await _model(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  @override
  Future<List<BookingModel>> getUserBookings({int page = 1}) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(
        ApiConstants.bookings,
        queryParameters: {'page': page, 'per_page': 50},
      );
      final items = response.data!['items'] as List<dynamic>;
      return await Future.wait(items.map((e) => _model(e as Map<String, dynamic>)));
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  @override
  Future<BookingModel> getBookingById(String id) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.booking(id));
      return await _model(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  @override
  Future<bool> cancelBooking(String bookingId, {String reason = 'Cancelled by customer'}) async {
    try {
      await apiClient.post<dynamic>(ApiConstants.cancelBooking(bookingId), data: {'reason': reason});
      return true;
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
