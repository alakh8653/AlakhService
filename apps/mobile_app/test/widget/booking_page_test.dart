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

/// user_service has one saved address; booking_service accepts the booking.
FakeAdapter server() => FakeAdapter((r) => r.path.endsWith('/addresses')
    ? (status: 200, body: [
        {'id': 'addr-1', 'label': 'Home', 'street': '12 MG Road', 'city': 'Pune', 'state': 'MH', 'postal_code': '411001', 'is_default': true},
      ])
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

    final sent = adapter.requests.singleWhere((r) => r.method == 'POST').data as Map;
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
