import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/booking_queue_api.dart';
import 'package:alakh_service/features/booking/presentation/widgets/live_queue_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Future<FakeAdapter> pump(WidgetTester tester, List<Map<String, Object?>> answers) async {
  var i = 0;
  final adapter = FakeAdapter((r) => (status: 200, body: answers[i < answers.length ? i++ : answers.length - 1]));
  final api = BookingQueueApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: LiveQueueCard(bookingId: 'b1', api: api, refreshEvery: const Duration(seconds: 30))),
  ));
  await tester.pumpAndSettle();
  return adapter;
}

const waiting = {
  'state': 'WAITING',
  'position': 3,
  'people_ahead': 2,
  'being_served': 2,
  'estimated_start': '2026-10-29T11:05:00Z',
  'wait_minutes': 45,
  'running_late_minutes': 50,
};

void main() {
  testWidgets('a waiting customer sees their place, wait, people ahead and how late the shop runs', (tester) async {
    final adapter = await pump(tester, [waiting, {...waiting, 'state': 'YOUR_TURN', 'position': 1, 'people_ahead': 0, 'wait_minutes': 0}]);
    expect(adapter.requests.single.path, endsWith('/bookings/b1/queue'));
    expect(find.text('Live queue at the shop'), findsOneWidget);
    expect(find.text('#3'), findsOneWidget);
    expect(find.text('About 45 min to wait'), findsOneWidget);
    expect(find.text('2 people ahead of you'), findsOneWidget);
    expect(find.text('Being served now: 2'), findsOneWidget);
    expect(find.text('The shop is running about 50 min late'), findsOneWidget);
    expect(find.textContaining('Expected around'), findsOneWidget);

    // It refreshes on its own: 30 seconds later it is their turn.
    await tester.pump(const Duration(seconds: 31));
    await tester.pumpAndSettle();
    expect(find.text("It's your turn!"), findsOneWidget);
    expect(find.text("Please go to the shop's counter now."), findsOneWidget);
  });

  testWidgets('a service in progress says so', (tester) async {
    await pump(tester, [{'state': 'IN_PROGRESS', 'being_served': 1}]);
    expect(find.text('Your service is in progress'), findsOneWidget);
    expect(find.textContaining('running'), findsNothing);
  });

  testWidgets('another day shows nothing and stops asking', (tester) async {
    final adapter = await pump(tester, [{'state': 'NOT_TODAY'}]);
    expect(find.text('Live queue at the shop'), findsNothing);
    await tester.pump(const Duration(minutes: 2));
    expect(adapter.requests, hasLength(1));
  });
}
