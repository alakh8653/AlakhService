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

  testWidgets('shows the range of the start, who serves them, and checks them in', (tester) async {
    final adapter = FakeAdapter((r) => r.method == 'POST'
        ? (status: 200, body: {...waiting, 'eta_min': '2026-10-29T10:55:00Z', 'eta_max': '2026-10-29T11:20:00Z', 'staff_name': 'Asha', 'checked_in': true, 'can_check_in': false})
        : (status: 200, body: {...waiting, 'eta_min': '2026-10-29T10:55:00Z', 'eta_max': '2026-10-29T11:20:00Z', 'staff_name': 'Asha', 'can_check_in': true, 'reason': 'PREFERRED_UNAVAILABLE'}));
    final api = BookingQueueApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: LiveQueueCard(bookingId: 'b1', api: api)))));
    await tester.pumpAndSettle();
    expect(find.textContaining('Expected between'), findsOneWidget);
    expect(find.text('With Asha'), findsOneWidget);
    expect(find.textContaining('chosen professional is away'), findsOneWidget);

    await tester.tap(find.text("I'm here"));
    await tester.pumpAndSettle();
    expect(adapter.requests.last.method, 'POST');
    expect(adapter.requests.last.path, endsWith('/bookings/b1/check-in'));
    expect(find.text("I'm here"), findsNothing);
    expect(find.text("You're checked in"), findsOneWidget);
  });

  testWidgets('late without checking in, or not possible today, says so', (tester) async {
    await pump(tester, [{'state': 'CHECK_IN_NEEDED', 'can_check_in': true}]);
    expect(find.textContaining('Check in when you arrive'), findsOneWidget);
    expect(find.text("I'm here"), findsOneWidget);
  });

  testWidgets('another day shows nothing and stops asking', (tester) async {
    final adapter = await pump(tester, [{'state': 'NOT_TODAY'}]);
    expect(find.text('Live queue at the shop'), findsNothing);
    await tester.pump(const Duration(minutes: 2));
    expect(adapter.requests, hasLength(1));
  });
}