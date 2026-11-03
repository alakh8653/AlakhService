import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:alakh_service/features/shop_owner/presentation/owner_reports_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Map<String, Object?> reportJson(String label, num profit, {num? change}) => {
      'label': label,
      'from': '2026-11-01',
      'to': '2026-11-30',
      'bookings': 3,
      'gross': 1500,
      'cash': 500,
      'online': 1000,
      'commission': 150,
      'gst': 27,
      'earned': 1323,
      'other_income': 0,
      'expenses': 1323 - profit,
      'profit': profit,
      'tips': 0,
      'profit_change_percent': change,
      'breakdown': [
        {'label': '2026-11-02', 'earned': 1323, 'expenses': 0, 'profit': profit},
      ],
    };

void main() {
  late FakeAdapter adapter;
  late List<Map<String, Object?>> entries;
  late List<String> sentTo;

  setUp(() {
    entries = [];
    sentTo = ['app', 'email'];
    adapter = FakeAdapter((RequestOptions r) {
      if (r.path.endsWith('/report')) {
        final period = r.queryParameters['period'];
        return (status: 200, body: period == 'yearly' ? reportJson('FY 2026-27', -200) : reportJson('November 2026', 1000, change: 12.5));
      }
      if (r.path.endsWith('/cash-entries') && r.method == 'POST') {
        entries.add({'id': 'e1', 'on_date': '2026-11-03', ...(r.data as Map<String, dynamic>)});
        return (status: 201, body: entries.last);
      }
      if (r.path.endsWith('/cash-entries')) return (status: 200, body: entries);
      if (r.path.contains('/cash-entries/')) {
        entries.clear();
        return (status: 204, body: null);
      }
      if (r.path.endsWith('/report/send')) return (status: 200, body: {'sent_to': sentTo});
      return (
        status: 200,
        body: {'daily': true, 'weekly': true, 'monthly': true, 'yearly': true, 'email': true, 'whatsapp': false},
      );
    });
  });

  ShopOwnerApi api() => ShopOwnerApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));

  Future<void> pump(WidgetTester tester) async {
    tester.view.physicalSize = const Size(1200, 3000);
    addTearDown(tester.view.resetPhysicalSize);
    await tester.pumpWidget(MaterialApp(home: OwnerReportsPage(shopId: 's1', api: api())));
    await tester.pumpAndSettle();
  }

  testWidgets('the profit comes first, and how it compares', (tester) async {
    await pump(tester);
    expect(find.text('Profit'), findsOneWidget);
    expect(find.text('₹1,000'), findsWidgets);
    expect(find.text('Up 12.5% on the period before'), findsOneWidget);
    expect(find.text('3 bookings completed'), findsOneWidget);
  });

  testWidgets('a loss is called a loss, and each period can be chosen', (tester) async {
    await pump(tester);
    await tester.tap(find.text('Yearly'));
    await tester.pumpAndSettle();
    expect(adapter.requests.last.path, contains('/cash-entries'));
    expect(find.text('FY 2026-27'), findsOneWidget);
    expect(find.text('Loss'), findsOneWidget);
  });

  testWidgets('an expense takes a tap and an amount, and can be removed', (tester) async {
    await pump(tester);
    await tester.tap(find.text('Add expense'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Spare parts'));
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pumpAndSettle();
    expect(find.text('Enter a number'), findsOneWidget);

    await tester.enterText(find.byKey(const ValueKey('entry-amount')), '450');
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pumpAndSettle();
    final saved = adapter.requests.firstWhere((r) => r.path.endsWith('/cash-entries') && r.method == 'POST');
    expect(saved.data['kind'], 'EXPENSE');
    expect(saved.data['category'], 'SPARE_PARTS');
    expect(saved.data['amount'], 450);
    expect(find.text('Spare parts'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.delete_outline));
    await tester.pumpAndSettle();
    expect(entries, isEmpty);
  });

  testWidgets('sending now says truthfully where it went', (tester) async {
    await pump(tester);
    await tester.tap(find.text('Send me this report now'));
    await tester.pumpAndSettle();
    expect(find.text('Sent to: email'), findsOneWidget);
    await tester.pump(const Duration(seconds: 5));
    await tester.pumpAndSettle();

    sentTo = ['app'];
    await tester.tap(find.text('Send me this report now'));
    await tester.pumpAndSettle();
    expect(find.textContaining("It's in your notifications"), findsOneWidget);
  });

  testWidgets('whatsapp stays off until the owner turns it on themselves', (tester) async {
    tester.view.physicalSize = const Size(1200, 3000);
    addTearDown(tester.view.resetPhysicalSize);
    await tester.pumpWidget(MaterialApp(home: OwnerReportSettingsPage(shopId: 's1', api: api())));
    await tester.pumpAndSettle();
    final toggle = find.byKey(const ValueKey('report-whatsapp'));
    expect(tester.widget<SwitchListTile>(toggle).value, isFalse);
    await tester.tap(toggle);
    await tester.pumpAndSettle();
    final saved = adapter.requests.lastWhere((r) => r.method == 'PUT');
    expect(saved.data['whatsapp'], isTrue);
    expect(saved.data['email'], isTrue);
  });
}
