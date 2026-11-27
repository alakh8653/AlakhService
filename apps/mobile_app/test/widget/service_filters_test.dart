import 'package:alakh_service/features/services/data/datasources/service_remote_datasource.dart';
import 'package:alakh_service/features/services/data/repositories/service_repository_impl.dart';
import 'package:alakh_service/features/services/domain/entities/service_filters.dart';
import 'package:alakh_service/features/services/domain/usecases/get_services_usecase.dart';
import 'package:alakh_service/features/services/domain/usecases/search_services_usecase.dart';
import 'package:alakh_service/features/services/presentation/bloc/service_bloc.dart';
import 'package:alakh_service/features/services/presentation/pages/service_list_page.dart';
import 'package:alakh_service/shared/service_types.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'services_pages_test.dart' show Online, clientFor, serviceJson;

/// The catalogue: answers with two services, the near one with its distance when given a location.
FakeAdapter catalogue() => FakeAdapter((r) {
      final located = r.queryParameters.containsKey('lat');
      return (
        status: 200,
        body: [
          {...serviceJson('Haircut', paise: 30000), 'shop_rating': 4.6, 'shop_rating_count': 38, if (located) 'distance_km': 1.04},
          {...serviceJson('Facial', paise: 90000), if (located) 'distance_km': 12.4},
        ],
      );
    });

Widget page(FakeAdapter adapter, {ServiceType? type, Future<(double, double)?> Function()? locate}) {
  final repo = ServiceRepositoryImpl(remoteDataSource: ServiceRemoteDataSourceImpl(apiClient: clientFor(adapter)), networkInfo: Online());
  return MaterialApp(
    home: BlocProvider(
      create: (_) => ServiceBloc(getServicesUseCase: GetServicesUseCase(repo), searchServicesUseCase: SearchServicesUseCase(repo)),
      child: ServiceListPage(type: type, locate: locate ?? () async => (18.5236, 73.8478)),
    ),
  );
}

Map<String, dynamic> lastQuery(FakeAdapter adapter) => adapter.requests.last.queryParameters;

void main() {
  test('filters become the catalogue query', () {
    expect(ServiceFilters.none.toQuery(), isEmpty);
    expect(
      const ServiceFilters(sort: ServiceSort.priceLow, homeVisit: true, minRating: 4, maxPrice: 500).toQuery(),
      {'sort': 'price_asc', 'mode': 'AT_HOME', 'min_rating': 4.0, 'max_price': 500.0},
    );
    // Nearest needs a place; without one it is left to the default order.
    expect(const ServiceFilters(sort: ServiceSort.nearest).toQuery(), isEmpty);
    expect(const ServiceFilters(sort: ServiceSort.nearest, latitude: 1, longitude: 2).toQuery(),
        {'sort': 'distance', 'lat': 1.0, 'lng': 2.0});
  });

  testWidgets('home visit, rating and price filters narrow the list', (tester) async {
    final adapter = catalogue();
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();
    expect(lastQuery(adapter).containsKey('mode'), isFalse);

    await tester.tap(find.byKey(const ValueKey('filter-home-visit')));
    await tester.pumpAndSettle();
    expect(lastQuery(adapter)['mode'], 'AT_HOME');

    await tester.tap(find.byKey(const ValueKey('filter-rating')));
    await tester.pumpAndSettle();
    expect(lastQuery(adapter)['min_rating'], 4.0);

    await tester.ensureVisible(find.byKey(const ValueKey('filter-price')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('filter-price')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Under ₹500'));
    await tester.pumpAndSettle();
    expect(lastQuery(adapter)['max_price'], 500.0);
    expect(find.text('Under ₹500'), findsOneWidget); // the chip says the limit

    await tester.ensureVisible(find.byKey(const ValueKey('filter-clear')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('filter-clear')));
    await tester.pumpAndSettle();
    expect(lastQuery(adapter).keys, containsAll(['skip', 'limit']));
    expect(lastQuery(adapter).keys.toSet().intersection({'mode', 'min_rating', 'max_price', 'sort'}), isEmpty);
  });

  testWidgets('nearest first asks for the location and shows how far each one is', (tester) async {
    final adapter = catalogue();
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('filter-sort')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Nearest first'));
    await tester.pumpAndSettle();

    expect(lastQuery(adapter), containsPair('sort', 'distance'));
    expect(lastQuery(adapter), containsPair('lat', 18.5236));
    expect(find.textContaining('1.0 km away'), findsOneWidget);
    expect(find.textContaining('12 km away'), findsOneWidget);
  });

  testWidgets('without the location, nearest first explains and leaves the order as it was', (tester) async {
    final adapter = catalogue();
    await tester.pumpWidget(page(adapter, locate: () async => null));
    await tester.pumpAndSettle();
    final before = adapter.requests.length;

    await tester.tap(find.byKey(const ValueKey('filter-sort')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Nearest first'));
    await tester.pumpAndSettle();

    expect(find.text("Allow location to see what's nearest to you"), findsOneWidget);
    expect(adapter.requests.length, before);
  });

  testWidgets('browsing a type from home sends the type, even before any search', (tester) async {
    final adapter = catalogue();
    await tester.pumpWidget(page(adapter, type: serviceTypes.first));
    await tester.pumpAndSettle();
    final RequestOptions r = adapter.requests.last;
    expect(r.queryParameters['category'], serviceTypes.first.id);
  });
}
