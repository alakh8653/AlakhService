import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/network_info.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/directions/data/shop_location_api.dart';
import 'package:alakh_service/features/queue/data/queue_api.dart';
import 'package:alakh_service/features/reviews/data/reviews_api.dart';
import 'package:alakh_service/features/reviews/presentation/all_reviews_page.dart';
import 'package:alakh_service/features/services/data/datasources/service_remote_datasource.dart';
import 'package:alakh_service/features/services/data/repositories/service_repository_impl.dart';
import 'package:alakh_service/features/services/domain/entities/service_entity.dart';
import 'package:alakh_service/features/services/domain/usecases/get_services_usecase.dart';
import 'package:alakh_service/features/services/domain/usecases/search_services_usecase.dart';
import 'package:alakh_service/features/services/presentation/bloc/service_bloc.dart';
import 'package:alakh_service/features/services/presentation/pages/service_detail_page.dart';
import 'package:alakh_service/features/services/presentation/pages/service_list_page.dart';
import 'package:alakh_service/shared/widgets/rating_widget.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

class Online implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

ApiClient clientFor(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

Map<String, dynamic> serviceJson(String name, String shopId) => {
      'id': name,
      'shop_id': shopId,
      'name': name,
      'price_cents': 30000,
      'duration_minutes': 30,
      'is_active': true,
    };

Map<String, dynamic> reviewJson(String id, int stars, {String? comment, String? reply}) => {
      'id': id,
      'shop_id': 'shop-1',
      'service_id': 'svc',
      'rating': stars,
      'comment': comment,
      'reviewer_name': 'Priya S.',
      'created_at': '2026-10-12T09:30:00Z',
      'reply': reply == null
          ? null
          : {'text': reply, 'created_at': '2026-10-13T09:30:00Z', 'updated_at': '2026-10-14T09:30:00Z'},
    };

const summaryJson = {
  'shop_id': 'shop-1',
  'average_rating': 4.6,
  'review_count': 128,
  'distribution': [
    {'stars': 5, 'count': 100},
    {'stars': 4, 'count': 20},
    {'stars': 3, 'count': 5},
    {'stars': 2, 'count': 2},
    {'stars': 1, 'count': 1},
  ],
};

/// shop_service and service_catalog for a shop with 128 reviews; [rating] filters, paging by skip.
FakeAdapter backend({int total = 128}) => FakeAdapter((r) {
      if (r.path.endsWith('/shops/ratings')) {
        return (status: 200, body: [
          {'shop_id': 'shop-1', 'average_rating': 4.6, 'review_count': 128},
          {'shop_id': 'shop-2', 'average_rating': 0.0, 'review_count': 0},
        ]);
      }
      if (r.path.endsWith('/reviews/summary')) return (status: 200, body: summaryJson);
      if (r.path.endsWith('/reviews')) {
        final stars = r.queryParameters['rating'] as int?;
        final skip = r.queryParameters['skip'] as int;
        final items = stars == 1 ? <Object>[] : [
          reviewJson('r${skip + 1}', stars ?? 5, comment: 'Lovely haircut, on time.', reply: 'Thank you, Priya!'),
          reviewJson('r${skip + 2}', stars ?? 4),
        ];
        return (status: 200, body: {'items': items, 'total': stars == 1 ? 0 : total});
      }
      if (r.path.contains('/shops/')) return (status: 200, body: {'name': 'Demo Salon', 'address': '12 MG Road'});
      if (r.path.endsWith('/services')) {
        return (status: 200, body: [serviceJson('Haircut', 'shop-1'), serviceJson('Facial', 'shop-2')]);
      }
      return (status: 200, body: <Object>[]);
    });

const service = ServiceEntity(
  id: 'svc', name: 'Haircut', description: '', category: '', basePrice: 300, priceUnit: '30 min', shopId: 'shop-1',
);

Widget detail(ApiClient c) => MaterialApp(
      home: ServiceDetailPage(service: service, shopApi: ShopLocationApi(c), queueApi: QueueApi(c), reviewsApi: ReviewsApi(c)),
    );

void main() {
  testWidgets('service cards show their shop rating, or New, from one ratings request', (tester) async {
    final adapter = backend();
    final client = clientFor(adapter);
    final repo = ServiceRepositoryImpl(
      remoteDataSource: ServiceRemoteDataSourceImpl(apiClient: client, ratings: ReviewsApi(client)),
      networkInfo: Online(),
    );
    await tester.pumpWidget(MaterialApp(
      home: BlocProvider(
        create: (_) => ServiceBloc(getServicesUseCase: GetServicesUseCase(repo), searchServicesUseCase: SearchServicesUseCase(repo)),
        child: const ServiceListPage(),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('4.6 (128)'), findsOneWidget);
    expect(find.text('New'), findsOneWidget);
    // Each card is read as one button, its rating in words.
    expect(find.bySemanticsLabel(RegExp('Rated 4.6 out of 5 from 128 reviews')), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('New, no reviews yet')), findsOneWidget);
    final ratingCalls = adapter.requests.where((r) => r.path.endsWith('/shops/ratings')).toList();
    expect(ratingCalls, hasLength(1));
    expect(ratingCalls.single.queryParameters['ids'], 'shop-1,shop-2');
  });

  test('services still list when ratings cannot be loaded', () async {
    final adapter = FakeAdapter((r) => r.path.endsWith('/shops/ratings')
        ? (status: 503, body: {'detail': 'down'})
        : (status: 200, body: [serviceJson('Haircut', 'shop-1')]));
    final client = clientFor(adapter);
    final source = ServiceRemoteDataSourceImpl(apiClient: client, ratings: ReviewsApi(client));
    final services = await source.getServices();
    expect(services.single.name, 'Haircut');
    expect(services.single.reviewCount, 0);
  });

  testWidgets('the detail page shows the summary, recent reviews with replies, and all reviews by stars', (tester) async {
    final semantics = tester.ensureSemantics();
    final adapter = backend();
    await tester.pumpWidget(detail(clientFor(adapter)));
    await tester.pumpAndSettle();

    expect(find.text('4.6 (128 reviews)'), findsOneWidget);
    expect(find.bySemanticsLabel('Rated 4.6 out of 5 from 128 reviews'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('See all reviews (128)'), 200);
    expect(find.text('Ratings & reviews'), findsOneWidget);
    expect(find.bySemanticsLabel('5 stars: 100 reviews'), findsOneWidget);
    expect(find.bySemanticsLabel('1 star: 1 review'), findsOneWidget);
    expect(find.text('Lovely haircut, on time.'), findsOneWidget);
    expect(find.text('12 Oct 2026'), findsNWidgets(2)); // Indian order: day, month, year
    expect(find.text('Reply from the shop · 14 Oct 2026'), findsOneWidget);
    expect(find.text('Thank you, Priya!'), findsOneWidget);
    expect(find.bySemanticsLabel('5 out of 5 stars'), findsWidgets);
    final recent = adapter.requests.where((r) => r.path.endsWith('/reviews')).single;
    expect(recent.queryParameters['limit'], 3);

    await tester.ensureVisible(find.text('See all reviews (128)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('See all reviews (128)'));
    await tester.pumpAndSettle();
    expect(find.byType(AllReviewsPage), findsOneWidget);
    expect(find.text('Reviews of Demo Salon'), findsOneWidget);
    expect(find.text('Show more reviews'), findsOneWidget);

    await tester.tap(find.text('Show more reviews'));
    await tester.pumpAndSettle();
    expect(adapter.requests.last.queryParameters['skip'], 2);

    await tester.tap(find.text('5 ★'));
    await tester.pumpAndSettle();
    expect(adapter.requests.last.queryParameters, containsPair('rating', 5));
    expect(adapter.requests.last.queryParameters['skip'], 0);
    expect(find.bySemanticsLabel('5 stars only'), findsOneWidget);

    await tester.tap(find.text('1 ★'));
    await tester.pumpAndSettle();
    expect(find.text('No 1-star reviews yet.'), findsOneWidget);
    semantics.dispose();
  });

  testWidgets('a shop without reviews reads as New and says so', (tester) async {
    final adapter = FakeAdapter((r) {
      if (r.path.endsWith('/reviews/summary')) {
        return (status: 200, body: {
          'average_rating': 0.0,
          'review_count': 0,
          'distribution': [for (final s in [5, 4, 3, 2, 1]) {'stars': s, 'count': 0}],
        });
      }
      if (r.path.endsWith('/reviews')) return (status: 200, body: {'items': <Object>[], 'total': 0});
      if (r.path.contains('/shops/')) return (status: 200, body: {'name': 'Demo Salon'});
      return (status: 200, body: <Object>[]);
    });
    await tester.pumpWidget(detail(clientFor(adapter)));
    await tester.pumpAndSettle();

    expect(find.text('New, no reviews yet'), findsOneWidget);
    await tester.scrollUntilVisible(find.textContaining('No reviews yet.'), 200);
    expect(find.textContaining('See all reviews'), findsNothing);
  });

  test('ReviewsApi reads summaries and pages and asks for ratings of distinct shops', () async {
    final adapter = backend(total: 7);
    final api = ReviewsApi(clientFor(adapter));

    final summary = await api.summary('shop-1');
    expect((summary.average, summary.count, summary.countFor(4)), (4.6, 128, 20));

    final page = await api.reviews('shop-1', skip: 4, limit: 2, rating: 4);
    expect(page.total, 7);
    expect(page.items.first.rating, 4);
    expect(page.items.first.reply!.text, 'Thank you, Priya!');
    expect(page.items.last.reply, isNull);
    expect(adapter.requests.last.queryParameters, {'skip': 4, 'limit': 2, 'rating': 4});

    final ratings = await api.ratings(['shop-1', 'shop-2', 'shop-1']);
    expect(ratings['shop-1']!.average, 4.6);
    expect(adapter.requests.last.queryParameters['ids'], 'shop-1,shop-2');
    expect(await api.ratings(const []), isEmpty);
  });

  test('star ratings are read out in words', () {
    expect(starsLabel(4), '4 out of 5 stars');
    expect(starsLabel(4.6), '4.6 out of 5 stars');
  });
}
