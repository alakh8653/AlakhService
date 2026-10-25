import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';
import '../../booking/data/models/booking_model.dart';
import '../../booking/domain/entities/booking.dart';
import '../../services/data/datasources/service_remote_datasource.dart';

/// The next step a provider takes on a job, if any.
class JobStep {
  final String status;
  final String label;

  const JobStep(this.status, this.label);

  static JobStep? after(String status) => switch (status) {
        BookingStatus.assigned => const JobStep(BookingStatus.enRoute, 'Start travelling'),
        BookingStatus.enRoute => const JobStep(BookingStatus.inProgress, 'Start job'),
        BookingStatus.inProgress => const JobStep(BookingStatus.completed, 'Complete job'),
        _ => null,
      };
}

/// Jobs assigned to the signed-in user as a provider (booking_service).
class JobsApi {
  final ApiClient apiClient;
  final ServiceRemoteDataSource? services;
  final Map<String, String> _serviceNames = {};

  JobsApi(this.apiClient, {this.services});

  /// While one of these is under way the provider's location is shared with the customer.
  static const sharingStatuses = {BookingStatus.enRoute, BookingStatus.inProgress};

  Future<String?> _serviceName(String serviceId) async {
    if (_serviceNames.containsKey(serviceId)) return _serviceNames[serviceId];
    try {
      final name = (await services?.getServiceById(serviceId))?.name;
      if (name != null) _serviceNames[serviceId] = name;
      return name;
    } catch (_) {
      return null;
    }
  }

  Future<BookingModel> _model(Map<String, dynamic> json) async =>
      BookingModel.fromJson(json, serviceName: await _serviceName(json['service_id'] as String));

  Future<List<Booking>> list({int perPage = 50}) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(
        ApiConstants.assignedBookings,
        queryParameters: {'per_page': perPage},
      );
      final items = response.data!['items'] as List<dynamic>;
      return await Future.wait(items.map((e) => _model(e as Map<String, dynamic>)));
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// Whether the user has ever been given a job, i.e. should see the Jobs tab.
  Future<bool> hasJobs() async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(
        ApiConstants.assignedBookings,
        queryParameters: {'per_page': 1},
      );
      return ((response.data!['total'] as num?) ?? 0) > 0;
    } on DioException {
      return false;
    }
  }

  Future<Booking> moveTo(String bookingId, String status) async {
    try {
      final response = await apiClient.put<Map<String, dynamic>>(
        ApiConstants.bookingStatus(bookingId),
        data: {'status': status},
      );
      return await _model(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
