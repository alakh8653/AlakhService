import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

class QueueTicket {
  final String queueId;
  final String? entryId;
  final int position;
  final int? estimatedWaitMinutes;

  const QueueTicket({required this.queueId, this.entryId, required this.position, this.estimatedWaitMinutes});

  factory QueueTicket.fromJson(Map<String, dynamic> json) => QueueTicket(
        queueId: json['queue_id'] as String,
        entryId: json['id'] as String?,
        position: (json['position'] as num).toInt(),
        estimatedWaitMinutes: (json['estimated_wait_minutes'] as num?)?.toInt(),
      );
}

/// Walk-in queues for a service (queue_service).
class QueueApi {
  final ApiClient apiClient;

  QueueApi(this.apiClient);

  Future<T> _call<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// The id of a queue currently taking customers for [serviceId], if any.
  Future<String?> openQueueFor(String serviceId) => _call(() async {
        final response = await apiClient.get<List<dynamic>>(ApiConstants.queues, queryParameters: {'service_id': serviceId});
        final queues = response.data ?? [];
        return queues.isEmpty ? null : (queues.first as Map<String, dynamic>)['id'] as String;
      });

  Future<QueueTicket> join({required String queueId, required String serviceId, required String customerId}) =>
      _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(
          ApiConstants.joinQueue(queueId),
          data: {'customer_id': customerId, 'service_id': serviceId},
        );
        return QueueTicket.fromJson(response.data!);
      });

  /// The customer's place in the queue, or null once they are no longer waiting.
  Future<QueueTicket?> position({required String queueId, required String customerId}) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.queuePosition(queueId, customerId));
      return QueueTicket.fromJson(response.data!);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      throw toServerException(e);
    }
  }

  Future<void> leave({required String queueId, required String entryId}) =>
      _call(() => apiClient.delete<dynamic>(ApiConstants.leaveQueue(queueId, entryId)));
}
