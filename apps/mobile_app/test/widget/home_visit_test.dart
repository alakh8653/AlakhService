import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/home_arrival_api.dart';
import 'package:alakh_service/features/booking/presentation/widgets/home_arrival_card.dart';
import 'package:alakh_service/features/jobs/data/jobs_api.dart';
import 'package:alakh_service/features/jobs/data/location_reporter.dart';
import 'package:alakh_service/features/jobs/presentation/jobs_page.dart';
import 'package:alakh_service/features/tracking/data/tracking_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart';

import '../support/fake_adapter.dart';

ApiClient clientFor(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

String clock(String iso) => DateFormat('h:mm a').format(DateTime.parse(iso).toLocal());

class _StaticSource implements LocationSource {
  @override
  Future<Fix?> current() async => const Fix(18.5, 73.8);
}

Future<void> pumpCard(WidgetTester tester, Map<String, Object?> body) async {
  final adapter = FakeAdapter((_) => (status: 200, body: body));
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: HomeArrivalCard(key: UniqueKey(), bookingId: 'b1', api: HomeArrivalApi(clientFor(adapter)))),
  ));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('a planned home visit shows the arrival, its range and the visits before it', (tester) async {
    await pumpCard(tester, {
      'state': 'PLANNED',
      'scheduled_at': '2026-10-29T05:30:00Z',
      'arrive_at': '2026-10-29T05:40:00Z',
      'arrive_min': '2026-10-29T05:35:00Z',
      'arrive_max': '2026-10-29T05:55:00Z',
      'jobs_before': 2,
      'late_minutes': 10,
    });
    expect(find.text('Your home visit'), findsOneWidget);
    expect(find.text('Your professional arrives around ${clock('2026-10-29T05:40:00Z')}'), findsOneWidget);
    expect(find.text('Between ${clock('2026-10-29T05:35:00Z')} and ${clock('2026-10-29T05:55:00Z')}'), findsOneWidget);
    expect(find.text('2 visits before yours'), findsOneWidget);
    expect(find.text('Running about 10 min behind your booked time'), findsOneWidget);
  });

  testWidgets('on the way, and with the customer', (tester) async {
    await pumpCard(tester, {'state': 'ON_THE_WAY', 'scheduled_at': '2026-10-29T05:30:00Z', 'arrive_at': '2026-10-29T05:35:00Z'});
    expect(find.text('On the way, arriving around ${clock('2026-10-29T05:35:00Z')}'), findsOneWidget);
    await pumpCard(tester, {'state': 'ARRIVED', 'scheduled_at': '2026-10-29T05:30:00Z'});
    expect(find.text('Your professional is with you'), findsOneWidget);
    await pumpCard(tester, {'state': 'NOT_ASSIGNED', 'scheduled_at': '2026-10-29T05:30:00Z'});
    expect(find.text('Your home visit'), findsNothing);
  });

  testWidgets("the professional's jobs say when to leave for each home visit", (tester) async {
    final adapter = FakeAdapter((r) {
      if (r.path.endsWith('/assigned/route')) {
        return (
          status: 200,
          body: [
            {
              'booking_id': 'j1',
              'booking_number': 'BK-9',
              'customer_display_name': 'Ravi',
              'state': 'PLANNED',
              'scheduled_at': '2026-10-12T05:30:00Z',
              'arrive_at': '2026-10-12T05:30:00Z',
              'leave_at': '2026-10-12T05:10:00Z',
              'finish_at': '2026-10-12T06:15:00Z',
              'travel_minutes': 20,
              'late_minutes': 0,
            }
          ]
        );
      }
      if (r.path.startsWith('/api/v1/services')) return (status: 404, body: {});
      return (
        status: 200,
        body: {
          'items': [
            {
              'id': 'j1',
              'booking_number': 'BK-9',
              'customer_id': 'c1',
              'provider_id': 'p1',
              'service_id': 's1',
              'status': 'ASSIGNED',
              'service_mode': 'AT_HOME',
              'scheduled_at': '2026-10-12T05:30:00Z',
              'total_amount': 49900,
              'created_at': '2026-10-11T05:30:00Z',
            }
          ],
          'total': 1
        }
      );
    });
    final client = clientFor(adapter);
    final reporter = LocationReporter(tracking: TrackingApi(client), source: _StaticSource(), providerId: 'p1');
    await tester.pumpWidget(MaterialApp(
      home: JobsPage(providerId: 'p1', jobsApi: JobsApi(client), reporter: reporter, routeApi: HomeArrivalApi(client)),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Leave by ${clock('2026-10-12T05:10:00Z')} · 20 min drive'), findsOneWidget);
  });
}
