import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/network_info.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/directions/data/shop_location_api.dart';
import 'package:alakh_service/features/queue/data/queue_api.dart';
import 'package:alakh_service/features/reviews/data/reviews_api.dart';
import 'package:alakh_service/features/services/data/datasources/service_remote_datasource.dart';
import 'package:alakh_service/features/services/data/repositories/service_repository_impl.dart';
import 'package:alakh_service/features/services/domain/entities/service_entity.dart';
import 'package:alakh_service/features/services/domain/usecases/get_services_usecase.dart';
import 'package:alakh_service/features/services/domain/usecases/search_services_usecase.dart';
import 'package:alakh_service/features/services/presentation/bloc/service_bloc.dart';
import 'package:alakh_service/features/services/presentation/pages/service_detail_page.dart';
import 'package:alakh_service/features/services/presentation/pages/service_list_page.dart';
import 'package:alakh_service/features/shops/data/shop_hours_api.dart';
import 'package:alakh_service/shared/widgets/service_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

class Online implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

Map<String, dynamic> serviceJson(String name, {int paise = 450000, List<String> modes = const ['AT_SHOP']}) => {
      'id': name,
      'shop_id': 'shop-1',
      'name': name,
      'price_cents': paise,
      'duration_minutes': 120,
      'is_active': true,
      'service_modes': modes,
      'pickup_fee_cents': 9900,
    };

ApiClient clientFor(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

void main() {
  testWidgets('search waits for typing to pause, then sends one request', (tester) async {
    final adapter = FakeAdapter((r) => (
          status: 200,
          body: r.path.endsWith('/search') ? [serviceJson('Haircut')] : [serviceJson('Haircut'), serviceJson('AC repair')],
        ));
    final repo = ServiceRepositoryImpl(remoteDataSource: ServiceRemoteDataSourceImpl(apiClient: clientFor(adapter)), networkInfo: Online());
    await tester.pumpWidget(MaterialApp(
      home: BlocProvider(
        create: (_) => ServiceBloc(getServicesUseCase: GetServicesUseCase(repo), searchServicesUseCase: SearchServicesUseCase(repo)),
        child: const ServiceListPage(),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('AC repair'), findsOneWidget);

    for (final partial in ['h', 'ha', 'hai', 'hair']) {
      await tester.enterText(find.byType(TextField), partial);
      await tester.pump(const Duration(milliseconds: 100));
    }
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();

    final searches = adapter.requests.where((r) => r.path.endsWith('/search')).toList();
    expect(searches, hasLength(1));
    expect(searches.single.queryParameters['q'], 'hair');
    expect(find.text('AC repair'), findsNothing);
    expect(find.byTooltip('Clear search'), findsOneWidget);

    await tester.tap(find.byTooltip('Clear search'));
    await tester.pumpAndSettle();
    expect(find.text('AC repair'), findsOneWidget);
  });

  testWidgets('nothing found says so and offers all services', (tester) async {
    final adapter = FakeAdapter((r) => (status: 200, body: r.path.endsWith('/search') ? <Object>[] : [serviceJson('Haircut')]));
    final repo = ServiceRepositoryImpl(remoteDataSource: ServiceRemoteDataSourceImpl(apiClient: clientFor(adapter)), networkInfo: Online());
    await tester.pumpWidget(MaterialApp(
      home: BlocProvider(
        create: (_) => ServiceBloc(getServicesUseCase: GetServicesUseCase(repo), searchServicesUseCase: SearchServicesUseCase(repo)),
        child: const ServiceListPage(initialQuery: 'yoga'),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Nothing found for "yoga"'), findsOneWidget);
    await tester.tap(find.text('Show all services'));
    await tester.pumpAndSettle();
    expect(find.text('Haircut'), findsOneWidget);
  });

  testWidgets('a service card shows Indian rupees, how it is offered, and "New" instead of 0.0 (0)', (tester) async {
    const service = ServiceEntity(
      id: 's', name: 'Laptop screen repair', description: '', category: 'Service', basePrice: 4500, priceUnit: '120 min',
      durationMinutes: 120, serviceModes: [ServiceMode.atShop, ServiceMode.pickupDrop],
    );
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: ServiceCard(service: service))));

    expect(find.text('₹4,500'), findsOneWidget);
    expect(find.text('At shop · Pickup & drop'), findsOneWidget);
    expect(find.text('New'), findsOneWidget);
    expect(find.text('0.0'), findsNothing);
    expect(find.text('Service'), findsNothing); // the meaningless default category is hidden
  });

  testWidgets('service details name the shop and list each way to get it with its fee', (tester) async {
    final adapter = FakeAdapter((r) => r.path.endsWith('/hours')
        ? (status: 200, body: {
            'configured': true,
            'weekly': [
              {'day': 6, 'intervals': [{'start': '10:00', 'end': '14:00'}, {'start': '16:00', 'end': '20:00'}]},
            ],
            'holidays': <Object>[],
          })
        : r.path.contains('/shops/')
        ? (status: 200, body: {'name': 'Demo Salon', 'address': '12 MG Road', 'city': 'Pune'})
        : (status: 200, body: <Object>[]));
    final client = clientFor(adapter);
    const service = ServiceEntity(
      id: 's', name: 'Laptop screen repair', description: '', category: '', basePrice: 4500, priceUnit: '120 min',
      shopId: 'shop-1', serviceModes: [ServiceMode.atShop, ServiceMode.pickupDrop], pickupFee: 99,
    );
    await tester.pumpWidget(MaterialApp(
      home: ServiceDetailPage(
        service: service,
        shopApi: ShopLocationApi(client),
        queueApi: QueueApi(client),
        reviewsApi: ReviewsApi(client),
        hoursApi: ShopHoursApi(client),
        clock: () => DateTime.utc(2026, 10, 18, 9), // Sunday 2:30 PM in India, between the two shifts
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Closed · opens 4 PM'), findsOneWidget);

    expect(find.text('Demo Salon · 12 MG Road, Pune'), findsOneWidget);
    expect(find.text('At the shop'), findsOneWidget);
    expect(find.text('Pickup & drop'), findsOneWidget);
    expect(find.text('+₹99'), findsOneWidget);
    expect(find.text('₹4,500'), findsOneWidget); // in the bar with Book Now, always on screen
    expect(find.text('Book Now'), findsOneWidget);
  });

  testWidgets('an unavailable service explains why it cannot be booked', (tester) async {
    final client = clientFor(FakeAdapter((_) => (status: 200, body: <Object>[])));
    const service = ServiceEntity(
      id: 's', name: 'Haircut', description: '', category: '', basePrice: 300, priceUnit: 'visit', isAvailable: false,
    );
    await tester.pumpWidget(MaterialApp(home: ServiceDetailPage(service: service, queueApi: QueueApi(client))));
    await tester.pumpAndSettle();

    expect(find.text("This service isn't taking bookings right now."), findsOneWidget);
    final button = tester.widget<ElevatedButton>(find.ancestor(of: find.text('Book Now'), matching: find.byType(ElevatedButton)));
    expect(button.onPressed, isNull);
  });
}
