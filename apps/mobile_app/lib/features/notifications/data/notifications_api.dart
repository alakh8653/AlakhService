import 'dart:convert';

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

  /// The booking it is about, and the event (booking.extras_requested...), from its data.
  final String? bookingId;
  final String? event;

  const AppNotification({
    required this.id,
    required this.title,
    required this.body,
    required this.channel,
    required this.isRead,
    required this.createdAt,
    this.bookingId,
    this.event,
  });

  /// notification_service keeps the event's data as a JSON string (or, from some senders, an object).
  static Map<String, dynamic> _data(Object? raw) {
    try {
      final decoded = raw is String ? jsonDecode(raw) : raw;
      return decoded is Map<String, dynamic> ? decoded : const {};
    } catch (_) {
      return const {};
    }
  }

  factory AppNotification.fromJson(Map<String, dynamic> json) {
    final data = _data(json['data']);
    return AppNotification(
        id: json['id'] as String,
        title: (json['title'] as String?) ?? '',
        body: (json['body'] as String?) ?? '',
        channel: (json['channel'] as String?) ?? 'in_app',
        isRead: (json['is_read'] as bool?) ?? false,
        createdAt: DateTime.tryParse((json['created_at'] as String?) ?? '')?.toLocal() ?? DateTime.now(),
        bookingId: data['booking_id']?.toString(),
        event: data['event']?.toString(),
      );
  }

  AppNotification read() => AppNotification(
        id: id,
        title: title,
        body: body,
        channel: channel,
        isRead: true,
        createdAt: createdAt,
        bookingId: bookingId,
        event: event,
      );
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
