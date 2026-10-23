import 'dart:async';

import 'package:alakh_service/app/app_links.dart';
import 'package:alakh_service/app/link_handler.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_event.dart';
import 'package:alakh_service/features/push/push_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'auth_flow_test.dart' show FakeAuth, blocFor;

/// The device's push channel, driven by the test.
class FakePushMessaging implements PushMessaging {
  final tokenRefresh = StreamController<String>.broadcast();
  final foregroundMessages = StreamController<PushMessage>.broadcast();
  final opened = StreamController<PushMessage>.broadcast();
  PushMessage? launch;
  String? token = 'fcm-token-1';
  int permissionRequests = 0;
  int deletes = 0;

  @override
  String get platform => 'android';

  @override
  Future<bool> requestPermission() async {
    permissionRequests++;
    return true;
  }

  @override
  Future<String?> getToken() async => token;

  @override
  Future<void> deleteToken() async => deletes++;

  @override
  Stream<String> get onTokenRefresh => tokenRefresh.stream;

  @override
  Stream<PushMessage> get onForegroundMessage => foregroundMessages.stream;

  @override
  Stream<PushMessage> get onOpenedApp => opened.stream;

  @override
  Future<PushMessage?> initialMessage() async => launch;
}

class _Opened extends StatelessWidget {
  final AppTarget target;

  const _Opened(this.target);

  @override
  Widget build(BuildContext context) => Scaffold(body: Text('opened $target'));
}

void main() {
  late FakePushMessaging messaging;
  late FakeAdapter server;
  late PushService push;
  late AuthBloc auth;
  late StreamController<Uri> links;

  // Made inside each test, so their streams run on the test's clock.
  void setUpApp() {
    messaging = FakePushMessaging();
    server = FakeAdapter((_) => (status: 201, body: {'id': 't1'}));
    push = PushService(
      messaging: messaging,
      api: DeviceTokenApi(ApiClient(dio: fakeDio(server), tokens: MemoryTokenStore())),
    );
    auth = blocFor(FakeAuth());
    links = StreamController<Uri>.broadcast();
  }

  setUp(setUpApp);

  Future<void> pumpApp(WidgetTester tester, {PushMessage? launch}) async {
    setUpApp();
    messaging.launch = launch;
    final navigatorKey = GlobalKey<NavigatorState>();
    final messengerKey = GlobalKey<ScaffoldMessengerState>();
    await tester.pumpWidget(BlocProvider.value(
      value: auth,
      child: LinkHandler(
        navigatorKey: navigatorKey,
        messengerKey: messengerKey,
        links: links.stream,
        push: push,
        pageFor: (target) => _Opened(target),
        child: MaterialApp(
          navigatorKey: navigatorKey,
          scaffoldMessengerKey: messengerKey,
          home: const Scaffold(body: Text('home')),
        ),
      ),
    ));
    await tester.pumpAndSettle();
  }

  Future<void> signIn(WidgetTester tester) async {
    auth.add(const OtpVerificationRequested(phone: '9876543210', otp: '123456'));
    await tester.pumpAndSettle();
  }

  Iterable<Map> registrations() =>
      server.requests.where((r) => r.path == '/api/v1/notifications/device-tokens').map((r) => r.data as Map);

  testWidgets('registers the device token after sign-in and again when it changes, deletes it on logout',
      (tester) async {
    await pumpApp(tester);
    expect(registrations(), isEmpty, reason: 'nobody signed in yet');

    await signIn(tester);
    expect(registrations().single, {'user_id': 'u1', 'token': 'fcm-token-1', 'platform': 'android'});

    messaging.tokenRefresh.add('fcm-token-2');
    await tester.pumpAndSettle();
    expect(registrations().last['token'], 'fcm-token-2');

    auth.add(const LogoutRequested());
    await tester.pumpAndSettle();
    expect(messaging.deletes, 1);
    messaging.tokenRefresh.add('fcm-token-3');
    await tester.pumpAndSettle();
    expect(registrations().map((r) => r['token']), isNot(contains('fcm-token-3')));
  });

  testWidgets('a tapped chat notification opens the chat; a booking one, the booking', (tester) async {
    await pumpApp(tester);
    await signIn(tester);

    messaging.opened.add(const PushMessage(data: {'event': 'booking.message', 'booking_id': 'b1'}));
    await tester.pumpAndSettle();
    expect(find.text('opened ${const BookingTarget('b1', chat: true)}'), findsOneWidget);

    messaging.opened.add(const PushMessage(data: {'event': 'booking.confirmed', 'booking_id': 'b2'}));
    await tester.pumpAndSettle();
    expect(find.text('opened ${const BookingTarget('b2')}'), findsOneWidget);
  });

  testWidgets('a foreground message shows in the app, with View opening its booking', (tester) async {
    await pumpApp(tester);
    await signIn(tester);

    messaging.foregroundMessages.add(const PushMessage(
      title: 'New message',
      body: 'Shop: Your bike is ready',
      data: {'event': 'booking.message', 'booking_id': 'b1'},
    ));
    await tester.pumpAndSettle();
    expect(find.text('New message\nShop: Your bike is ready'), findsOneWidget);

    await tester.tap(find.text('View'));
    await tester.pumpAndSettle();
    expect(find.text('opened ${const BookingTarget('b1', chat: true)}'), findsOneWidget);
  });

  testWidgets('a notification that launched the app, or a booking link, opens after sign-in', (tester) async {
    await pumpApp(tester, launch: const PushMessage(data: {'event': 'booking.confirmed', 'booking_id': 'b9'}));
    expect(find.text('home'), findsOneWidget);

    await signIn(tester);
    expect(find.text('opened ${const BookingTarget('b9')}'), findsOneWidget);
  });

  testWidgets('app links open the booking, and the reset link even when signed out', (tester) async {
    await pumpApp(tester);
    links.add(Uri.parse('https://$appLinkDomain/reset-password?token=abc'));
    await tester.pumpAndSettle();
    expect(find.text('opened ${const ResetPasswordTarget('abc')}'), findsOneWidget);

    links.add(Uri.parse('https://$appLinkDomain/b/b5'));
    await tester.pumpAndSettle();
    expect(find.text('opened ${const BookingTarget('b5')}'), findsNothing, reason: 'waits for sign-in');
    await signIn(tester);
    expect(find.text('opened ${const BookingTarget('b5')}'), findsOneWidget);
  });

  testWidgets('asks for notification permission once', (tester) async {
    await push.askPermission();
    await push.askPermission();
    expect(messaging.permissionRequests, 1);
  });

  test('without Firebase the push layer does nothing', () async {
    final none = PushService(messaging: null, api: DeviceTokenApi(ApiClient(dio: fakeDio(server), tokens: MemoryTokenStore())));
    await none.start();
    await none.onSignedIn('u1');
    await none.askPermission();
    await none.onSignedOut();
    expect(server.requests, isEmpty);
  });
}
