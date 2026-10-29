import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/shop_line/data/shop_line_api.dart';
import 'package:alakh_service/features/shop_line/presentation/shop_line_page.dart';
import 'package:alakh_service/shared/widgets/bottom_nav_bar.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

const shop = OwnedShop('s1', 'Asha Salon', {'svc1': 'Haircut'});

Map<String, Object?> entry(String id, String name, {String state = 'WAITING', int? position, bool noShow = false}) => {
      'booking_id': id,
      'booking_number': 'BK$id',
      'customer_display_name': name,
      'state': state,
      'position': position,
      'scheduled_at': '2026-10-29T05:00:00Z',
      'estimated_start': '2026-10-29T05:30:00Z',
      'running_late_minutes': 0,
      'service_id': 'svc1',
      'staff_id': 'st-a',
      'staff_name': 'Asha',
      'source': 'BOOKED',
      'priority': 'APPOINTMENT',
      'can_mark_no_show': noShow,
    };

final asha = {'staff_id': 'st-a', 'name': 'Asha', 'status': 'AVAILABLE', 'waiting': 2};

Future<FakeAdapter> pumpLine(WidgetTester tester) async {
  final adapter = FakeAdapter((RequestOptions r) {
    if (r.path.endsWith('/queue') && r.method == 'GET') {
      return (status: 200, body: [entry('b1', 'Ravi', position: 1), entry('b2', 'Kiran', position: 2, noShow: true)]);
    }
    if (r.path.endsWith('/queue/team')) return (status: 200, body: [asha]);
    if (r.path.endsWith('/walk-ins')) return (status: 201, body: entry('b3', 'Neha', position: 3));
    if (r.path.endsWith('/call-next')) return (status: 200, body: entry('b1', 'Ravi', state: 'IN_PROGRESS'));
    return (status: 200, body: <String, Object?>{});
  });
  final api = ShopLineApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));
  await tester.pumpWidget(MaterialApp(home: ShopLinePage(shop: shop, api: api)));
  await tester.pumpAndSettle();
  return adapter;
}

void main() {
  testWidgets("the owner sees today's line and the team, and calls the next customer", (tester) async {
    final adapter = await pumpLine(tester);
    expect(find.text('Asha Salon'), findsOneWidget);
    expect(find.text('2 waiting'), findsOneWidget);
    expect(find.text('Ravi'), findsOneWidget);
    expect(find.textContaining('Haircut · Asha'), findsNWidgets(2));
    expect(find.text('#1'), findsOneWidget);

    await tester.tap(find.text('Next customer'));
    await tester.pumpAndSettle();
    final call = adapter.requests.firstWhere((r) => r.path.endsWith('/call-next'));
    expect(call.data, {'staff_id': 'st-a'});

    await tester.tap(find.text('Break 15 min'));
    await tester.pumpAndSettle();
    final brk = adapter.requests.firstWhere((r) => r.path.endsWith('/team/st-a'));
    expect(brk.method, 'PUT');
    expect(brk.data, {'status': 'BREAK', 'minutes': 15});
  });

  testWidgets('a walk-in is added from the counter and a no-show marked', (tester) async {
    final adapter = await pumpLine(tester);
    await tester.tap(find.text('Add a walk-in'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Neha');
    await tester.tap(find.text('Add'));
    await tester.pumpAndSettle();
    final add = adapter.requests.firstWhere((r) => r.path.endsWith('/walk-ins'));
    expect(add.data, {'service_id': 'svc1', 'name': 'Neha'});
    expect(find.text('Neha is #3 in line'), findsOneWidget);

    await tester.tap(find.byType(PopupMenuButton<int>).at(1)); // Kiran
    await tester.pumpAndSettle();
    await tester.tap(find.text('No-show'));
    await tester.pumpAndSettle();
    expect(adapter.requests.any((r) => r.method == 'POST' && r.path.endsWith('/bookings/b2/no-show')), isTrue);
  });

  testWidgets('My shop shows in the bar only for shop owners', (tester) async {
    Future<void> bar(bool owner) => tester.pumpWidget(MaterialApp(
          home: Scaffold(bottomNavigationBar: AppBottomNavBar(currentIndex: 0, onTap: (_) {}, showShopLine: owner)),
        ));
    await bar(false);
    expect(find.text('My shop'), findsNothing);
    await bar(true);
    expect(find.text('My shop'), findsOneWidget);
  });
}
