import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

class AppNotification {
  final String id;
  final String title;
  final String body;
  final String channel;
  final bool isRead;
  final DateTime createdAt;

  const AppNotification({
    required this.id,
    required this.title,
    required this.body,
    required this.channel,
    required this.isRead,
    required this.createdAt,
  });

  factory AppNotification.fromJson(Map<String, dynamic> json) => AppNotification(
        id: json['id'] as String,
        title: (json['title'] as String?) ?? '',
        body: (json['body'] as String?) ?? '',
        channel: (json['channel'] as String?) ?? 'in_app',
        isRead: (json['is_read'] as bool?) ?? false,
        createdAt: DateTime.tryParse((json['created_at'] as String?) ?? '')?.toLocal() ?? DateTime.now(),
      );

  AppNotification read() =>
      AppNotification(id: id, title: title, body: body, channel: channel, isRead: true, createdAt: createdAt);
}

/// The signed-in user's notifications (notification_service).
class NotificationsApi {
  final ApiClient apiClient;

  NotificationsApi(this.apiClient);

  Future<T> _call<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  Future<List<AppNotification>> list({bool unreadOnly = false}) => _call(() async {
        final response = await apiClient.get<Map<String, dynamic>>(
          ApiConstants.notifications,
          queryParameters: {'unread_only': unreadOnly, 'per_page': 50},
        );
        return (response.data!['items'] as List<dynamic>)
            .map((e) => AppNotification.fromJson(e as Map<String, dynamic>))
            .toList();
      });

  Future<int> unreadCount() => _call(() async {
        final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.unreadCount);
        return (response.data!['unread_count'] as num).toInt();
      });

  Future<void> markRead(String id) => _call(() => apiClient.post<dynamic>(ApiConstants.markRead(id)));

  Future<void> markAllRead() => _call(() => apiClient.post<dynamic>(ApiConstants.markAllRead));
}
