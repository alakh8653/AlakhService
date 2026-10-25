import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import '../../app/app_links.dart';
import '../../core/constants/api_constants.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_errors.dart';

/// A push notification as the app sees it.
class PushMessage {
  final String? title;
  final String? body;
  final Map<String, dynamic> data;

  const PushMessage({this.title, this.body, this.data = const {}});
}

/// The device's push channel (Firebase Cloud Messaging in the app, a fake in tests).
abstract class PushMessaging {
  /// 'android' or 'ios', as notification_service records the token.
  String get platform;

  /// Asks to show notifications (Android 13+ and iOS); true when allowed.
  Future<bool> requestPermission();
  Future<String?> getToken();
  Future<void> deleteToken();
  Stream<String> get onTokenRefresh;

  /// Messages arriving while the app is on screen (the system shows none then).
  Stream<PushMessage> get onForegroundMessage;

  /// Notifications tapped while the app was in the background.
  Stream<PushMessage> get onOpenedApp;

  /// The notification that launched the app, if one did.
  Future<PushMessage?> initialMessage();
}

/// Starts Firebase, or returns null when this build has no Firebase config: the app then runs
/// without push. Config goes in android/app/google-services.json and
/// ios/Runner/GoogleService-Info.plist (see the app's README).
Future<PushMessaging?> initFirebasePush() async {
  try {
    await Firebase.initializeApp();
    return FirebasePushMessaging(FirebaseMessaging.instance);
  } catch (e) {
    debugPrint('Push notifications are off: Firebase is not configured ($e)');
    return null;
  }
}

class FirebasePushMessaging implements PushMessaging {
  final FirebaseMessaging messaging;

  FirebasePushMessaging(this.messaging);

  static PushMessage _message(RemoteMessage m) =>
      PushMessage(title: m.notification?.title, body: m.notification?.body, data: m.data);

  @override
  String get platform => defaultTargetPlatform == TargetPlatform.iOS ? 'ios' : 'android';

  @override
  Future<bool> requestPermission() async {
    final settings = await messaging.requestPermission();
    return settings.authorizationStatus == AuthorizationStatus.authorized ||
        settings.authorizationStatus == AuthorizationStatus.provisional;
  }

  // notification_service sends with the classic FCM registration token (messages:send "token"), so
  // these stay on the token API rather than the newer installation-id registration.
  @override
  // ignore: deprecated_member_use
  Future<String?> getToken() => messaging.getToken();

  @override
  // ignore: deprecated_member_use
  Future<void> deleteToken() => messaging.deleteToken();

  @override
  // ignore: deprecated_member_use
  Stream<String> get onTokenRefresh => messaging.onTokenRefresh;

  @override
  Stream<PushMessage> get onForegroundMessage => FirebaseMessaging.onMessage.map(_message);

  @override
  Stream<PushMessage> get onOpenedApp => FirebaseMessaging.onMessageOpenedApp.map(_message);

  @override
  Future<PushMessage?> initialMessage() async {
    final m = await messaging.getInitialMessage();
    return m == null ? null : _message(m);
  }
}

/// notification_service's device tokens: POST /api/v1/notifications/device-tokens
/// {user_id, token, platform}, and .../unregister {token} on sign-out. Re-registering a token
/// moves it to the user now signed in.
class DeviceTokenApi {
  final ApiClient apiClient;

  DeviceTokenApi(this.apiClient);

  Future<void> register({required String userId, required String token, required String platform}) async {
    try {
      await apiClient.post<dynamic>(
        ApiConstants.deviceTokens,
        data: {'user_id': userId, 'token': token, 'platform': platform},
      );
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  Future<void> unregister(String token) async {
    try {
      await apiClient.post<dynamic>('${ApiConstants.deviceTokens}/unregister', data: {'token': token});
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}

/// Keeps this device's push token registered for the signed-in user and turns notifications into
/// app targets. Without [messaging] (no Firebase config) everything is a no-op.
class PushService {
  final PushMessaging? messaging;
  final DeviceTokenApi api;

  PushService({required this.messaging, required this.api});

  final _taps = StreamController<AppTarget>.broadcast();
  final _foreground = StreamController<PushMessage>.broadcast();
  final List<StreamSubscription<Object?>> _subscriptions = [];
  StreamSubscription<String>? _refresh;
  String? _userId;
  AppTarget? _launchTarget;

  /// Where tapped notifications lead.
  Stream<AppTarget> get taps => _taps.stream;

  /// Messages that arrived while the app was open, to show in the app.
  Stream<PushMessage> get foreground => _foreground.stream;

  /// The target of the notification that launched the app, taken once.
  AppTarget? takeLaunchTarget() {
    final target = _launchTarget;
    _launchTarget = null;
    return target;
  }

  /// Listens for notifications. Call once at start-up.
  Future<void> start() async {
    final m = messaging;
    if (m == null) return;
    _subscriptions
      ..add(m.onForegroundMessage.listen(_foreground.add))
      ..add(m.onOpenedApp.listen((message) {
        final target = pushTarget(message.data);
        if (target != null) _taps.add(target);
      }));
    try {
      final initial = await m.initialMessage();
      if (initial != null) _launchTarget = pushTarget(initial.data);
    } catch (_) {}
  }

  /// Registers the token for [userId] now and whenever it changes.
  Future<void> onSignedIn(String userId) async {
    final m = messaging;
    if (m == null) return;
    _userId = userId;
    _refresh?.cancel();
    _refresh = m.onTokenRefresh.listen(_register);
    try {
      final token = await m.getToken();
      if (token != null) await _register(token);
    } catch (e) {
      debugPrint('Could not register for push: $e');
    }
  }

  Future<void> _register(String token) async {
    final userId = _userId;
    if (userId == null) return;
    try {
      await api.register(userId: userId, token: token, platform: messaging!.platform);
    } catch (e) {
      debugPrint('Could not register the push token: $e');
    }
  }

  /// Called while signing out, before the session ends: notification_service turns this device's
  /// token off. Best effort; [onSignedOut] deletes the token itself anyway.
  Future<void> releaseDevice() async {
    final m = messaging;
    if (m == null) return;
    try {
      final token = await m.getToken();
      if (token != null) await api.unregister(token);
    } catch (_) {}
  }

  /// Stops pushes to this device for the user who signed out: the token is deleted, so FCM rejects
  /// it even if [releaseDevice] could not reach the server. The next sign-in registers a new one.
  Future<void> onSignedOut() async {
    _userId = null;
    _refresh?.cancel();
    _refresh = null;
    try {
      await messaging?.deleteToken();
    } catch (_) {}
  }

  bool _asked = false;

  /// Asks for permission to show notifications, once per run: after the customer books, when
  /// updates from the shop start to matter. Android 13+ and iOS show the system prompt; it is a
  /// no-op where permission was already decided.
  Future<void> askPermission() async {
    final m = messaging;
    if (m == null || _asked) return;
    _asked = true;
    try {
      await m.requestPermission();
    } catch (_) {}
  }

  Future<void> dispose() async {
    for (final s in _subscriptions) {
      await s.cancel();
    }
    await _refresh?.cancel();
    await _taps.close();
    await _foreground.close();
  }
}
