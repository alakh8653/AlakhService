import 'package:alakh_service/app/app_links.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/models/booking_model.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/data/trust_api.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_details_page.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/jobs/data/location_reporter.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/directions/data/shop_location_api.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:alakh_service/features/tracking/data/tracking_api.dart';
import 'package:alakh_service/features/tracking/data/tracking_destination.dart';
import 'package:alakh_service/features/tracking/presentation/pages/live_tracking_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_history_page_test.dart' show Online, booking;

final future = DateTime.now().add(const Duration(days: 3)).toUtc().toIso8601String();

/// booking_service with booking [b] and the trust endpoints.
FakeAdapter trustServer(Map<String, dynamic> b, {int sosStatus = 201}) {
  final current = b;
  return FakeAdapter((r) {
    if (r.path.endsWith('/payments')) return (status: 200, body: <Object>[]);
    if (r.path.endsWith('/messages')) {
      return (status: 200, body: {'items': <Object>[], 'total': 0, 'page': 1, 'per_page': 1, 'unread': 0, 'can_send': true});
    }
    if (r.path.endsWith('/share')) {
      return (status: 201, body: {'url': 'https://alakhservice.in/s/tok123', 'expires_at': '2026-11-05T10:00:00Z'});
    }
    if (r.path.endsWith('/sos')) {
      return (status: sosStatus, body: sosStatus < 300 ? {'alert_id': 'a1', 'emergency_number': '112'} : {'detail': 'Not Found'});
    }
    if (r.path.endsWith('/rework')) return (status: 201, body: {...booking('b9', 'PENDING', future), 'rework_of': 'b1', 'total_amount': 0});
    if (r.path.endsWith('/b9')) return (status: 200, body: {...booking('b9', 'PENDING', future), 'rework_of': 'b1', 'total_amount': 0});
    return (status: 200, body: current);
  });
}

class NoFix implements LocationSource {
  @override
  Future<Fix?> current() async => null;
}

class Opened {
  final shared = <String>[];
  final uris = <Uri>[];
}

Widget details(
  FakeAdapter adapter, {
  String id = 'b1',
  Opened? opened,
  DateTime Function()? clock,
  Future<Fix?> Function()? location,
}) {
  final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
  return MaterialApp(
    home: BookingDetailsPage(
      bookingId: id,
      repository: BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online()),
      paymentApi: PaymentApi(client),
      chatApi: ChatApi(client),
      trustApi: TrustApi(client),
      shareText: (text) async => opened?.shared.add(text),
      openUri: (uri) async {
        opened?.uris.add(uri);
        return true;
      },
      sosLocation: location ?? () async => const Fix(18.52, 73.85),
      clock: clock ?? DateTime.now,
    ),
  );
}

Future<void> pumpDetails(WidgetTester tester, Widget app) async {
  tester.view.physicalSize = const Size(1200, 4000);
  addTearDown(tester.view.resetPhysicalSize);
  await tester.pumpWidget(app);
  await tester.pumpAndSettle();
}

Iterable<RequestOptions> posts(FakeAdapter a, String suffix) =>
    a.requests.where((r) => r.method == 'POST' && r.path.endsWith(suffix));

void main() {
  test('tapping a notification about a booking opens it', () {
    expect(pushTarget({'event': 'booking.status_changed', 'booking_id': 'b1'}), const BookingTarget('b1'));
  });

  group('start code', () {
    testWidgets('a home visit shows the code to give the professional on arrival', (tester) async {
      final adapter = trustServer({...booking('b1', 'ASSIGNED', future), 'service_mode': 'AT_HOME', 'start_code': '4821'});
      await pumpDetails(tester, details(adapter));
      expect(find.text('4821'), findsOneWidget);
      expect(find.text('Share this code only when the professional arrives'), findsOneWidget);
    });

    testWidgets('no code at the shop, or once the work has started', (tester) async {
      await pumpDetails(tester, details(trustServer({...booking('b1', 'CONFIRMED', future), 'start_code': '4821'})));
      expect(find.text('4821'), findsNothing);
      await tester.pumpWidget(Container());
      await pumpDetails(
        tester,
        details(trustServer({...booking('b1', 'IN_PROGRESS', future), 'service_mode': 'AT_HOME', 'start_code': '4821'})),
      );
      expect(find.text('4821'), findsNothing);
    });
  });

  group('free fix', () {
    final completedAt = DateTime(2026, 11, 1, 12);
    Map<String, dynamic> done({String? reworkId}) => {
          ...booking('b1', 'COMPLETED', completedAt.toUtc().toIso8601String()),
          'guarantee_until': DateTime(2026, 11, 8, 12).toUtc().toIso8601String(),
          if (reworkId != null) 'rework_booking_id': reworkId,
        };

    testWidgets('within the guarantee the customer asks for a free fix and is taken to it', (tester) async {
      final adapter = trustServer(done());
      await pumpDetails(tester, details(adapter, clock: () => DateTime(2026, 11, 3, 9)));
      expect(find.textContaining('Free fix guarantee until'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('request-rework')));
      await tester.pumpAndSettle();
      expect(find.text('Request a free fix'), findsOneWidget);
      // Too short a reason is refused before anything is sent.
      await tester.enterText(find.byKey(const ValueKey('rework-reason')), 'Leaks');
      await tester.tap(find.byKey(const ValueKey('rework-send')));
      await tester.pumpAndSettle();
      expect(find.text('Please write at least 10 characters'), findsOneWidget);
      expect(posts(adapter, '/rework'), isEmpty);

      await tester.enterText(find.byKey(const ValueKey('rework-reason')), 'The tap leaks again since yesterday');
      await tester.tap(find.byKey(const ValueKey('rework-send')));
      await tester.pumpAndSettle();
      final sent = posts(adapter, '/bookings/b1/rework').single;
      expect(sent.data, {'reason': 'The tap leaks again since yesterday'});
      // The free-fix booking opens, and links back to the original.
      expect(find.text('This is a free fix for an earlier booking'), findsOneWidget);
      expect(find.text('See the original booking'), findsOneWidget);
    });

    testWidgets('after the guarantee, or once asked, there is no request button', (tester) async {
      await pumpDetails(tester, details(trustServer(done()), clock: () => DateTime(2026, 11, 20)));
      expect(find.textContaining('The free-fix guarantee ended'), findsOneWidget);
      expect(find.byKey(const ValueKey('request-rework')), findsNothing);

      await tester.pumpWidget(Container());
      await pumpDetails(tester, details(trustServer(done(reworkId: 'b9')), clock: () => DateTime(2026, 11, 3)));
      expect(find.byKey(const ValueKey('request-rework')), findsNothing);
      expect(find.text('See the free-fix booking'), findsOneWidget);
    });

    testWidgets('the server refusing (period over) is shown on the form', (tester) async {
      final adapter = FakeAdapter((r) => r.path.endsWith('/rework')
          ? (status: 409, body: {'detail': 'The free-fix period for this booking has ended'})
          : r.path.endsWith('/payments')
              ? (status: 200, body: <Object>[])
              : (status: 200, body: done()));
      await pumpDetails(tester, details(adapter, clock: () => DateTime(2026, 11, 3)));
      await tester.tap(find.byKey(const ValueKey('request-rework')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const ValueKey('rework-reason')), 'The fan stopped working again');
      await tester.tap(find.byKey(const ValueKey('rework-send')));
      await tester.pumpAndSettle();
      expect(find.text('The free-fix period for this booking has ended'), findsOneWidget);
    });
  });

  group('safety', () {
    Map<String, dynamic> visit(String status) =>
        {...booking('b1', status, future), 'service_mode': 'AT_HOME', 'provider_id': 'p1'};

    testWidgets('share visit status sends the link to the share sheet', (tester) async {
      final opened = Opened();
      final adapter = trustServer(visit('PROVIDER_EN_ROUTE'));
      await pumpDetails(tester, details(adapter, opened: opened));
      await tester.tap(find.byKey(const ValueKey('share-visit')));
      await tester.pumpAndSettle();
      expect(posts(adapter, '/bookings/b1/share'), hasLength(1));
      expect(opened.shared.single, contains('https://alakhservice.in/s/tok123'));
    });

    testWidgets('SOS asks first, sends the position, then offers to call 112', (tester) async {
      final opened = Opened();
      final adapter = trustServer(visit('IN_PROGRESS'));
      await pumpDetails(tester, details(adapter, opened: opened));
      await tester.tap(find.byKey(const ValueKey('sos-b1')));
      await tester.pumpAndSettle();
      expect(find.text('Send an SOS alert?'), findsOneWidget);
      await tester.tap(find.text('Not now'));
      await tester.pumpAndSettle();
      expect(posts(adapter, '/sos'), isEmpty);

      await tester.tap(find.byKey(const ValueKey('sos-b1')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('sos-confirm')));
      await tester.pumpAndSettle();
      expect(posts(adapter, '/bookings/b1/sos').single.data, {'lat': 18.52, 'lng': 73.85});
      expect(find.text('Our safety team has been alerted.'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('sos-call')));
      await tester.pumpAndSettle();
      expect(opened.uris.single.toString(), 'tel:112');
    });

    testWidgets('when the alert cannot be sent, calling 112 is still offered', (tester) async {
      final opened = Opened();
      final adapter = trustServer(visit('IN_PROGRESS'), sosStatus: 404);
      await pumpDetails(tester, details(adapter, opened: opened, location: () async => null));
      await tester.tap(find.byKey(const ValueKey('sos-b1')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('sos-confirm')));
      await tester.pumpAndSettle();
      expect(posts(adapter, '/sos').single.data, <String, dynamic>{});
      expect(find.textContaining('call 112 now'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('sos-call')));
      expect(opened.uris.single.scheme, 'tel');
    });

    testWidgets('no SOS or sharing for a visit to the shop', (tester) async {
      await pumpDetails(tester, details(trustServer({...booking('b1', 'IN_PROGRESS', future), 'provider_id': 'p1'})));
      expect(find.byKey(const ValueKey('sos-b1')), findsNothing);
      expect(find.byKey(const ValueKey('share-visit')), findsNothing);
    });

    testWidgets('live tracking offers sharing and SOS too', (tester) async {
      final opened = Opened();
      final adapter = trustServer(visit('PROVIDER_EN_ROUTE'));
      final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
      await tester.pumpWidget(MaterialApp(
        home: LiveTrackingPage(
          booking: BookingModel.fromJson(visit('PROVIDER_EN_ROUTE')),
          trackingApi: TrackingApi(client),
          destinations: TrackingDestinations(
            shops: ShopLocationApi(client),
            addresses: AddressApi(client),
            device: NoFix(),
          ),
          trustApi: TrustApi(client),
          shareText: (t) async => opened.shared.add(t),
          pollInterval: const Duration(hours: 1),
        ),
      ));
      await tester.pump();
      expect(find.byKey(const ValueKey('sos-b1')), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('share-visit')));
      await tester.pumpAndSettle();
      expect(opened.shared.single, contains('/s/tok123'));
    });
  });
}
