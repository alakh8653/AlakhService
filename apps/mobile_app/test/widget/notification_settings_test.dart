import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/notifications/data/notifications_api.dart';
import 'package:alakh_service/features/notifications/presentation/pages/notification_settings_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

void main() {
  testWidgets('switches save at once, and quiet hours default to 10 PM to 7 AM', (tester) async {
    Map<String, dynamic> stored = {'push': true, 'sms': true, 'email': true, 'quiet_hours': null};
    final adapter = FakeAdapter((r) {
      if (r.method == 'PUT') stored = Map<String, dynamic>.from(r.data as Map);
      return (status: 200, body: stored);
    });
    await tester.pumpWidget(MaterialApp(
      home: NotificationSettingsPage(api: NotificationsApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()))),
    ));
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(find.byKey(const ValueKey('pref-sms'))).value, isTrue);

    await tester.tap(find.byKey(const ValueKey('pref-sms')));
    await tester.pumpAndSettle();
    expect(stored['sms'], isFalse);
    expect(tester.widget<SwitchListTile>(find.byKey(const ValueKey('pref-sms'))).value, isFalse);

    await tester.tap(find.byKey(const ValueKey('pref-quiet')));
    await tester.pumpAndSettle();
    expect(stored['quiet_hours'], {'start': 22, 'end': 7});
    expect(find.byKey(const ValueKey('quiet-start')), findsOneWidget);
    expect(find.text('Whatever you switch off, every update still appears under Notifications in the app.'), findsOneWidget);
  });

  testWidgets('a failed save puts the switch back', (tester) async {
    final adapter = FakeAdapter((r) => r.method == 'PUT'
        ? (status: 503, body: {'detail': 'Try again in a minute'})
        : (status: 200, body: {'push': true, 'sms': true, 'email': true, 'quiet_hours': null}));
    await tester.pumpWidget(MaterialApp(
      home: NotificationSettingsPage(api: NotificationsApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()))),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('pref-email')));
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(find.byKey(const ValueKey('pref-email'))).value, isTrue);
    expect(find.text('Try again in a minute'), findsOneWidget);
  });
}
