import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/trust_api.dart';
import 'package:alakh_service/features/booking/domain/entities/booking.dart';
import 'package:alakh_service/features/booking/presentation/widgets/provider_trust.dart';
import 'package:alakh_service/features/jobs/data/jobs_api.dart';
import 'package:alakh_service/features/jobs/data/location_reporter.dart';
import 'package:alakh_service/features/jobs/presentation/jobs_page.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:alakh_service/features/shop_owner/presentation/owner_guarantee_page.dart';
import 'package:alakh_service/features/shop_owner/presentation/owner_home_page.dart';
import 'package:alakh_service/features/tracking/data/tracking_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../support/fake_adapter.dart';
import 'shop_owner_test.dart' show bookingJson, owned, shopJson, user;

class _NoFix implements LocationSource {
  @override
  Future<Fix?> current() async => null;
}

Map<String, dynamic> homeJob(String status, {Map<String, dynamic> extra = const {}}) => {
      'id': 'j1',
      'booking_number': 'BK-j1',
      'customer_id': 'c1',
      'provider_id': 'p1',
      'service_id': 's1',
      'shop_id': 'shop1',
      'status': status,
      'service_mode': 'AT_HOME',
      'scheduled_at': '2026-11-03T05:30:00Z',
      'total_amount': 49900,
      'notes': 'Address: 12 MG Road',
      'created_at': '2026-11-02T05:30:00Z',
      ...extra,
    };

/// booking_service for one job; status changes need [code], and answer 429 after [triesAllowed] wrong ones.
FakeAdapter jobServer(Map<String, dynamic> job, {String code = '4821', int triesAllowed = 5}) {
  var current = job;
  var wrong = 0;
  return FakeAdapter((r) {
    if (r.path == '/api/v1/locations') return (status: 201, body: {});
    if (r.path.startsWith('/api/v1/services')) return (status: 404, body: {});
    if (r.path.endsWith('/route')) return (status: 200, body: <Object>[]);
    if (r.path.endsWith('/status')) {
      final data = r.data as Map;
      final target = data['status'] as String;
      if (needsStartCode(current['service_mode'] as String, target) && data['start_code'] != code) {
        wrong++;
        if (wrong > triesAllowed) return (status: 429, body: {'detail': 'Too Many Requests'});
        return (status: 422, body: {'detail': 'Ask the customer for the 4-digit start code'});
      }
      current = {...current, 'status': target};
      return (status: 200, body: current);
    }
    if (r.path.endsWith('/sos')) return (status: 201, body: {'alert_id': 'a1', 'emergency_number': '112'});
    return (status: 200, body: {'items': [current], 'total': 1});
  });
}

Future<void> pumpJobs(WidgetTester tester, FakeAdapter adapter, {List<Uri>? opened}) async {
  tester.view.physicalSize = const Size(1200, 3000);
  addTearDown(tester.view.resetPhysicalSize);
  final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
  await tester.pumpWidget(MaterialApp(
    home: JobsPage(
      providerId: 'p1',
      jobsApi: JobsApi(client),
      reporter: LocationReporter(tracking: TrackingApi(client), source: _NoFix(), providerId: 'p1'),
      trustApi: TrustApi(client),
      openUri: (uri) async {
        opened?.add(uri);
        return true;
      },
      sosLocation: () async => null,
    ),
  ));
  await tester.pumpAndSettle();
}

Iterable<RequestOptions> puts(FakeAdapter a) => a.requests.where((r) => r.method == 'PUT');

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('only starting work at the customer\'s needs the code', () {
    expect(needsStartCode('AT_HOME', BookingStatus.inProgress), isTrue);
    expect(needsStartCode('PICKUP_DROP', BookingStatus.pickedUp), isTrue);
    expect(needsStartCode('PICKUP_DROP', BookingStatus.inProgress), isFalse);
    expect(needsStartCode('AT_SHOP', BookingStatus.inProgress), isFalse);
    expect(needsStartCode('AT_HOME', BookingStatus.enRoute), isFalse);
  });

  group('provider jobs', () {
    testWidgets('a home visit starts only with the customer\'s code, and wrong codes say why', (tester) async {
      final adapter = jobServer(homeJob('PROVIDER_EN_ROUTE'));
      await pumpJobs(tester, adapter);
      await tester.tap(find.text('Start job'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Ask the customer for the 4-digit start code'), findsOneWidget);

      // Backing out starts nothing.
      await tester.tap(find.text('Not now'));
      await tester.pumpAndSettle();
      expect(puts(adapter), isEmpty);

      await tester.tap(find.text('Start job'));
      await tester.pumpAndSettle();
      // Not 4 digits: refused on the phone.
      await tester.enterText(find.byKey(const ValueKey('start-code-field')), '12');
      await tester.tap(find.byKey(const ValueKey('start-code-submit')));
      await tester.pumpAndSettle();
      expect(puts(adapter), isEmpty);

      await tester.enterText(find.byKey(const ValueKey('start-code-field')), '1111');
      await tester.tap(find.byKey(const ValueKey('start-code-submit')));
      await tester.pumpAndSettle();
      expect(puts(adapter).single.data, {'status': 'IN_PROGRESS', 'start_code': '1111'});
      expect(find.text('Ask the customer for the 4-digit start code'), findsOneWidget);
      expect(find.text('Complete job'), findsNothing);

      await tester.enterText(find.byKey(const ValueKey('start-code-field')), '4821');
      await tester.tap(find.byKey(const ValueKey('start-code-submit')));
      await tester.pumpAndSettle();
      expect(puts(adapter).last.data, {'status': 'IN_PROGRESS', 'start_code': '4821'});
      expect(find.byKey(const ValueKey('start-code-field')), findsNothing);
      expect(find.text('Complete job'), findsOneWidget);
    });

    testWidgets('too many wrong codes are refused with a wait', (tester) async {
      final adapter = jobServer(homeJob('PROVIDER_EN_ROUTE'), triesAllowed: 0);
      await pumpJobs(tester, adapter);
      await tester.tap(find.text('Start job'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const ValueKey('start-code-field')), '0000');
      await tester.tap(find.byKey(const ValueKey('start-code-submit')));
      await tester.pumpAndSettle();
      expect(find.text('Too many wrong tries. Please wait 15 minutes and try again.'), findsOneWidget);
    });

    testWidgets('a free fix is labelled, and the provider has SOS on a home visit', (tester) async {
      final opened = <Uri>[];
      final adapter = jobServer(homeJob('IN_PROGRESS', extra: {'rework_of': 'old1', 'total_amount': 0}));
      await pumpJobs(tester, adapter, opened: opened);
      expect(find.text('Free fix'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('sos-j1')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('sos-confirm')));
      await tester.pumpAndSettle();
      expect(adapter.requests.where((r) => r.path.endsWith('/bookings/j1/sos')), hasLength(1));
      await tester.tap(find.byKey(const ValueKey('sos-call')));
      expect(opened.single.toString(), 'tel:112');
    });
  });

  group('owner', () {
    late FakeAdapter adapter;

    Future<void> pumpHome(WidgetTester tester, List<Map<String, Object?>> bookings, {String code = '4821'}) async {
      tester.view.physicalSize = const Size(1200, 4000);
      addTearDown(tester.view.resetPhysicalSize);
      adapter = FakeAdapter((r) {
        if (r.path.endsWith('/status')) {
          return r.data['start_code'] == code
              ? (status: 200, body: <String, Object?>{})
              : (status: 422, body: {'detail': 'Ask the customer for the 4-digit start code'});
        }
        if (r.path.endsWith('/bookings/shop/s1')) {
          return (status: 200, body: {'items': bookings, 'total': bookings.length, 'page': 1, 'per_page': 100});
        }
        if (r.path.endsWith('/services')) return (status: 200, body: [{'id': 'svc1', 'name': 'Fan repair', 'price_cents': 29900}]);
        if (r.path.endsWith('/shops/s1') && r.method == 'PUT') return (status: 200, body: shopJson());
        if (r.path.endsWith('/shops/s1')) return (status: 200, body: {...shopJson(), 'guarantee_days': 14});
        return (status: 200, body: <String, Object?>{});
      });
      final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
      await tester.pumpWidget(MaterialApp(
        home: OwnerHomePage(
          shop: owned,
          user: user,
          api: ShopOwnerApi(client),
          trustApi: TrustApi(client),
          refreshEvery: const Duration(hours: 1),
          sosLocation: () async => null,
        ),
      ));
      await tester.pumpAndSettle();
    }

    testWidgets('starting a home visit asks for the customer\'s code', (tester) async {
      await pumpHome(tester, [bookingJson('b1', 'PROVIDER_EN_ROUTE', mode: modeAtHome)]);
      await tester.tap(find.text('Start service'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const ValueKey('start-code-field')), '4821');
      await tester.tap(find.byKey(const ValueKey('start-code-submit')));
      await tester.pumpAndSettle();
      final put = adapter.requests.singleWhere((r) => r.method == 'PUT');
      expect(put.data, {'status': 'IN_PROGRESS', 'start_code': '4821'});
    });

    testWidgets('collecting an item for a pickup asks for the code; at the shop it does not', (tester) async {
      await pumpHome(tester, [
        bookingJson('b1', 'PROVIDER_EN_ROUTE', mode: modePickupDrop),
        bookingJson('b2', 'CONFIRMED', name: 'Shop S.'),
      ]);
      await tester.tap(find.text('Item picked up'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('start-code-field')), findsOneWidget);
      await tester.enterText(find.byKey(const ValueKey('start-code-field')), '9999');
      await tester.tap(find.byKey(const ValueKey('start-code-submit')));
      await tester.pumpAndSettle();
      expect(find.text('Ask the customer for the 4-digit start code'), findsOneWidget);
      await tester.tap(find.text('Not now'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Customer arrived'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('start-code-field')), findsNothing);
      expect(adapter.requests.where((r) => r.method == 'PUT').last.data, {'status': 'IN_PROGRESS'});
    });

    testWidgets('a free fix is labelled', (tester) async {
      await pumpHome(tester, [
        {...bookingJson('b1', 'CONFIRMED'), 'rework_of': 'old1', 'total_amount': 0},
        bookingJson('b2', 'CONFIRMED', name: 'Paid P.'),
      ]);
      expect(find.text('Free fix'), findsOneWidget);
    });

    testWidgets('SOS only when the owner is at the customer\'s home themselves', (tester) async {
      await pumpHome(tester, [
        {...bookingJson('b1', 'IN_PROGRESS', mode: modeAtHome), 'provider_id': 'u1'},
        {...bookingJson('b2', 'IN_PROGRESS', mode: modeAtHome, name: 'Staff S.'), 'provider_id': 'staff9'},
      ]);
      expect(find.byKey(const ValueKey('sos-b1')), findsOneWidget);
      expect(find.byKey(const ValueKey('sos-b2')), findsNothing);
    });

    testWidgets('the free-fix guarantee is set in days, 0 to 90', (tester) async {
      await pumpHome(tester, const []);
      await tester.tap(find.text('Free-fix guarantee'));
      await tester.pumpAndSettle();
      expect(find.text('14'), findsOneWidget);
      final field = find.descendant(of: find.byKey(const ValueKey('guarantee-days')), matching: find.byType(TextFormField));
      await tester.enterText(field, '120');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();
      expect(find.text('Enter a number from 0 to 90'), findsOneWidget);
      await tester.enterText(field, '30');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();
      final put = adapter.requests.singleWhere((r) => r.method == 'PUT');
      expect(put.path, endsWith('/shops/s1'));
      expect(put.data, {'guarantee_days': 30});
      expect(find.byType(OwnerGuaranteePage), findsNothing);
    });
  });
}
