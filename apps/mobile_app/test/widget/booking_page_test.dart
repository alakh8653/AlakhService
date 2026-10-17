import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/network_info.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/usecases/cancel_booking_usecase.dart';
import 'package:alakh_service/features/booking/domain/usecases/create_booking_usecase.dart';
import 'package:alakh_service/features/booking/presentation/bloc/booking_bloc.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_page.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:alakh_service/features/services/domain/entities/service_entity.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

class Online implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

/// user_service has one saved address; booking_service accepts the booking (after [failFirst] tries
/// that fail, as when the network drops).
FakeAdapter server({int failFirst = 0}) {
  var bookingTries = 0;
  return FakeAdapter((r) => r.path.endsWith('/addresses')
    ? (status: 200, body: [
        {'id': 'addr-1', 'label': 'Home', 'street': '12 MG Road', 'city': 'Pune', 'state': 'MH', 'postal_code': '411001', 'is_default': true},
      ])
    : ++bookingTries <= failFirst
    ? (status: 503, body: {'detail': 'Booking service unavailable'})
    : (status: 201, body: {
        'id': 'b1',
        'booking_number': 'BK1',
        'customer_id': 'u1',
        'service_id': 's1',
        'status': 'PENDING',
        'scheduled_at': '2026-11-01T05:00:00Z',
        'duration_minutes': 120,
        'total_amount': 459900,
        'service_mode': 'PICKUP_DROP',
        'created_at': '2026-10-16T00:00:00Z',
      }));
}

/// The Idempotency-Key header of each booking request sent so far.
List<Object?> keysSent(FakeAdapter adapter) =>
    adapter.requests.where((r) => r.method == 'POST').map((r) => r.headers['Idempotency-Key']).toList();

Widget page(FakeAdapter adapter, {List<String> modes = const [ServiceMode.atShop, ServiceMode.pickupDrop]}) {
  final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
  final repo = BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online());
  return MaterialApp(
    home: BlocProvider(
      create: (_) => BookingBloc(
        createBookingUseCase: CreateBookingUseCase(repo),
        cancelBookingUseCase: CancelBookingUseCase(repo),
        bookingRepository: repo,
      ),
      child: BookingPage(
        serviceId: 's1',
        serviceName: 'Laptop screen repair',
        servicePrice: 4500,
        addressApi: AddressApi(client),
        serviceModes: modes,
        pickupFee: 99,
      ),
    ),
  );
}

Future<void> pickDateAndTime(WidgetTester tester) async {
  await tester.tap(find.text('Select Date'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('OK'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Select Time'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('OK'));
  await tester.pumpAndSettle();
}

Future<void> confirm(WidgetTester tester) async {
  await tester.ensureVisible(find.text('Confirm Booking'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Confirm Booking'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('pickup & drop asks where to collect from and what, and sends it with the fee shown', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server();
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    // At the shop by default: no address or item needed.
    expect(find.text('Visit the shop'), findsOneWidget);
    expect(find.text('What should we collect?'), findsNothing);
    expect(find.text('Saved address'), findsNothing);
    expect(find.text('₹4500'), findsOneWidget);

    await tester.tap(find.text('Pickup & drop (+₹99)'));
    await tester.pumpAndSettle();
    expect(find.text('₹4599'), findsOneWidget); // the pickup fee is part of the price
    expect(find.text('Collect from'), findsOneWidget);
    expect(find.textContaining('Home: 12 MG Road'), findsOneWidget); // the default address is chosen

    await pickDateAndTime(tester);
    await confirm(tester);
    expect(adapter.requests.where((r) => r.method == 'POST'), isEmpty); // the item is required

    await tester.enterText(
      find.ancestor(of: find.textContaining('Honda Activa'), matching: find.byType(TextFormField)),
      'Dell XPS 13, cracked screen',
    );
    await confirm(tester);

    final request = adapter.requests.singleWhere((r) => r.method == 'POST');
    final sent = request.data as Map;
    expect(request.headers['Idempotency-Key'], matches(RegExp(r'^[0-9a-f]{32}$')));
    expect(sent['service_mode'], 'PICKUP_DROP');
    expect(sent['address_id'], 'addr-1');
    expect(sent['item_description'], 'Dell XPS 13, cracked screen');
    expect(sent['notes'], contains('Address: 12 MG Road'));
  });

  testWidgets('a shop-only service shows no choice and sends no address', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server();
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    expect(find.text('How would you like it?'), findsNothing);

    await pickDateAndTime(tester);
    await confirm(tester);
    final sent = adapter.requests.singleWhere((r) => r.method == 'POST').data as Map;
    expect(sent['service_mode'], 'AT_SHOP');
    expect(sent.containsKey('address_id'), isFalse);
    expect(sent['notes'], isNot(contains('Address:')));
  });

  testWidgets('a retry after an error sends the same Idempotency-Key; a changed booking gets a new one', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server(failFirst: 2);
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    await pickDateAndTime(tester);

    await confirm(tester);
    expect(find.text('Booking service unavailable'), findsOneWidget);
    await confirm(tester); // the customer taps again: the same attempt
    final keys = keysSent(adapter);
    expect(keys, hasLength(2));
    expect(keys[0], matches(RegExp(r'^[0-9a-f]{32}$')));
    expect(keys[1], keys[0]);
    final bodies = adapter.requests.where((r) => r.method == 'POST').map((r) => r.data).toList();
    expect(bodies[1], bodies[0]);

    // Something changed, so it is a different booking request and must not reuse the key.
    await tester.enterText(
      find.ancestor(of: find.text('Any special instructions...'), matching: find.byType(TextFormField)),
      'Please call on arrival',
    );
    await confirm(tester);
    final third = keysSent(adapter)[2];
    expect(third, matches(RegExp(r'^[0-9a-f]{32}$')));
    expect(third, isNot(keys[0]));
  });

  testWidgets('each new booking starts with its own Idempotency-Key', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final first = server();
    await tester.pumpWidget(page(first, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    await pickDateAndTime(tester);
    await confirm(tester);

    // Booked: the page closes. Booking again opens a new page.
    await tester.pumpWidget(const SizedBox());
    final second = server();
    await tester.pumpWidget(page(second, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    await pickDateAndTime(tester);
    await confirm(tester);

    expect(keysSent(first), hasLength(1));
    expect(keysSent(second), hasLength(1));
    expect(keysSent(second).single, isNot(keysSent(first).single));
  });

  test('mode labels and fees', () {
    expect(modeChoiceLabel(ServiceMode.atHome, 150), 'At my place (+₹150)');
    expect(modeChoiceLabel(ServiceMode.pickupDrop, 99.5), 'Pickup & drop (+₹99.50)');
    expect(modeChoiceLabel(ServiceMode.atShop, 0), 'Visit the shop');
    const service = ServiceEntity(
      id: 's', name: 'AC repair', description: '', category: '', basePrice: 799, priceUnit: 'visit',
      serviceModes: [ServiceMode.atHome], homeVisitFee: 99, pickupFee: 199,
    );
    expect([service.feeFor(ServiceMode.atHome), service.feeFor(ServiceMode.pickupDrop), service.feeFor(ServiceMode.atShop)], [99, 199, 0]);
  });
}
