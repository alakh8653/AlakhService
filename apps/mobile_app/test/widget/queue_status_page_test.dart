import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/queue/data/queue_api.dart';
import 'package:alakh_service/features/queue/presentation/pages/queue_status_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Widget page(QueueTicket ticket, FakeAdapter adapter) => MaterialApp(
      home: QueueStatusPage(
        ticket: ticket,
        customerId: 'u1',
        serviceName: 'Haircut',
        queueApi: QueueApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore())),
        pollInterval: const Duration(seconds: 1),
      ),
    );

/// Lets the page's request to the fake server complete and redraw (without waiting for the next poll).
Future<void> settle(WidgetTester tester) async {
  await tester.pump(const Duration(milliseconds: 50));
  await tester.pump();
}

void main() {
  testWidgets('a waiting customer sees people ahead, the wait and when they will be called', (tester) async {
    final callAt = DateTime(2026, 10, 16, 11, 40);
    final adapter = FakeAdapter((_) => (status: 200, body: {
          'queue_id': 'q1',
          'entry_id': 'e1',
          'status': 'WAITING',
          'position': 3,
          'people_ahead': 2,
          'estimated_wait_minutes': 30,
          'estimated_call_at': callAt.toUtc().toIso8601String(),
        }));
    // As joined: the join response has no people-ahead or call time; the page fetches them at once.
    await tester.pumpWidget(page(const QueueTicket(queueId: 'q1', entryId: 'e1', position: 3, estimatedWaitMinutes: 30), adapter));
    await settle(tester);

    expect(find.text('#3'), findsOneWidget);
    expect(find.text('30 min'), findsOneWidget);
    expect(find.text('Expected around 11:40 AM'), findsOneWidget);
    expect(find.text('2 people ahead of you'), findsOneWidget);
    expect(find.text('Leave Queue'), findsOneWidget);
  });

  testWidgets("when the shop calls them the page says it's their turn", (tester) async {
    final adapter = FakeAdapter((_) => (status: 200, body: {
          'queue_id': 'q1',
          'entry_id': 'e1',
          'status': 'CALLED',
          'position': 0,
          'people_ahead': 0,
          'estimated_wait_minutes': 0,
        }));
    await tester.pumpWidget(page(const QueueTicket(queueId: 'q1', entryId: 'e1', position: 1, estimatedWaitMinutes: 0), adapter));
    expect(find.text("You're next"), findsOneWidget); // before the server answers

    await settle(tester);
    expect(find.text("It's your turn!"), findsOneWidget);
    expect(find.text('Please go to the counter now.'), findsOneWidget);
    expect(find.text('Leave Queue'), findsNothing); // nothing to leave once called
  });

  testWidgets('once served the customer is told they are no longer in the queue', (tester) async {
    final adapter = FakeAdapter((_) => (status: 404, body: {'detail': 'Customer not in queue'}));
    await tester.pumpWidget(page(const QueueTicket(queueId: 'q1', entryId: 'e1', position: 1), adapter));
    await tester.pump(const Duration(seconds: 1));
    await tester.pump();
    expect(find.textContaining("You're no longer in this queue"), findsOneWidget);
  });

  testWidgets('leaving asks first, so a mis-tap does not lose the place', (tester) async {
    final adapter = FakeAdapter((r) => r.method == 'DELETE'
        ? (status: 204, body: null)
        : (status: 200, body: {'queue_id': 'q1', 'entry_id': 'e1', 'status': 'WAITING', 'position': 2, 'people_ahead': 1, 'estimated_wait_minutes': 10}));
    await tester.pumpWidget(page(const QueueTicket(queueId: 'q1', entryId: 'e1', position: 2), adapter));
    await settle(tester);

    await tester.tap(find.text('Leave Queue'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Leave the queue?'), findsOneWidget);
    await tester.tap(find.text('Stay in queue'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(adapter.requests.where((r) => r.method == 'DELETE'), isEmpty);

    await tester.tap(find.text('Leave Queue'));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Leave'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(adapter.requests.where((r) => r.method == 'DELETE'), hasLength(1));
  });

  test('labels', () {
    expect(aheadLabel(0), 'Nobody is ahead of you');
    expect(aheadLabel(1), '1 person ahead of you');
    expect(aheadLabel(4), '4 people ahead of you');
    expect(waitLabel(const QueueTicket(queueId: 'q', position: 1)), 'Not available yet');
    expect(waitLabel(const QueueTicket(queueId: 'q', position: 1, estimatedWaitMinutes: 12)), '12 min');
  });
}
