import 'package:alakh_service/app/shell_navigation.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/notifications/data/notifications_api.dart';
import 'package:alakh_service/features/notifications/presentation/pages/notifications_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Widget page(FakeAdapter adapter) => MaterialApp(
      home: NotificationsPage(notificationsApi: NotificationsApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()))),
    );

void main() {
  testWidgets('tapping a booking update marks it read and opens My Bookings', (tester) async {
    ShellTab? opened;
    void listener() => opened = ShellNavigation.instance.requested;
    ShellNavigation.instance.addListener(listener);
    addTearDown(() => ShellNavigation.instance.removeListener(listener));
    final adapter = FakeAdapter((r) => r.method == 'POST'
        ? (status: 200, body: {'updated': 1})
        : (status: 200, body: {
            'items': [
              {'id': 'n1', 'title': 'Booking confirmed', 'body': 'Demo Salon confirmed your haircut', 'is_read': false, 'created_at': DateTime.now().toUtc().toIso8601String()},
            ],
          }));
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Booking confirmed'));
    await tester.pumpAndSettle();

    expect(adapter.requests.where((r) => r.method == 'POST' && r.path.endsWith('/n1/read')), hasLength(1));
    expect(opened, ShellTab.bookings);
  });

  testWidgets('a failed load explains and can be retried', (tester) async {
    var calls = 0;
    final adapter = FakeAdapter((_) => ++calls == 1
        ? (status: 503, body: {'detail': 'Notifications are unavailable'})
        : (status: 200, body: {'items': <Object>[]}));
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    expect(find.text('Notifications are unavailable'), findsOneWidget);
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.text('No notifications yet'), findsOneWidget);
  });
}
