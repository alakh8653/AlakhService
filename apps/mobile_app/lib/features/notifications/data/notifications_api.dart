import 'dart:convert';

import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';
import '../../../offline/offline_queue.dart';
import '../../../offline/sync_manager.dart';

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

/// How someone wants to be told (notification_service): each channel on or off, and quiet hours (hours of
/// the day in India; null when there are none).
class NotificationPreferences {
  final bool push;
  final bool sms;
  final bool email;
  final int? quietStart;
  final int? quietEnd;

  const NotificationPreferences({
    this.push = true,
    this.sms = true,
    this.email = true,
    this.quietStart,
    this.quietEnd,
  });

  factory NotificationPreferences.fromJson(Map<String, dynamic> json) {
    final quiet = json['quiet_hours'] as Map<String, dynamic>?;
    return NotificationPreferences(
      push: (json['push'] as bool?) ?? true,
      sms: (json['sms'] as bool?) ?? true,
      email: (json['email'] as bool?) ?? true,
      quietStart: (quiet?['start'] as num?)?.toInt(),
      quietEnd: (quiet?['end'] as num?)?.toInt(),
    );
  }

  Map<String, dynamic> toJson() => {
        'push': push,
        'sms': sms,
        'email': email,
        'quiet_hours': quietStart == null || quietEnd == null ? null : {'start': quietStart, 'end': quietEnd},
      };

  NotificationPreferences copyWith({bool? push, bool? sms, bool? email}) => NotificationPreferences(
        push: push ?? this.push,
        sms: sms ?? this.sms,
        email: email ?? this.email,
        quietStart: quietStart,
        quietEnd: quietEnd,
      );

  NotificationPreferences withQuiet(int start, int end) =>
      NotificationPreferences(push: push, sms: sms, email: email, quietStart: start, quietEnd: end);

  NotificationPreferences withoutQuiet() => NotificationPreferences(push: push, sms: sms, email: email);
}

/// The signed-in user's notifications (notification_service).
class NotificationsApi {
  final ApiClient apiClient;

  /// Marks things read offline too, sending it once back online.
  final SyncManager? offline;

  NotificationsApi(this.apiClient, {this.offline});

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

  Future<NotificationPreferences> preferences() => _call(() async {
        final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.notificationPreferences);
        return NotificationPreferences.fromJson(response.data!);
      });

  Future<NotificationPreferences> savePreferences(NotificationPreferences prefs) => _call(() async {
        final response =
            await apiClient.put<Map<String, dynamic>>(ApiConstants.notificationPreferences, data: prefs.toJson());
        return NotificationPreferences.fromJson(response.data!);
      });

  Future<void> markRead(String id) => _mark(ApiConstants.markRead(id), 'notification-read:$id');

  Future<void> markAllRead() => _mark(ApiConstants.markAllRead, 'notification-read:all');

  Future<void> _mark(String path, String key) => _call(() async {
        final offline = this.offline;
        if (offline == null) {
          await apiClient.post<dynamic>(path);
        } else {
          await offline.send(offline.request(PendingKind.notificationRead, 'POST', path, replaces: key));
        }
      });
}
