import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/core/theme/app_theme.dart';
import 'package:alakh_service/features/booking/presentation/widgets/trust_cards.dart';
import 'package:alakh_service/features/directions/data/shop_location_api.dart';
import 'package:alakh_service/features/notifications/data/notifications_api.dart';
import 'package:alakh_service/features/notifications/presentation/pages/notifications_page.dart';
import 'package:alakh_service/features/reviews/data/reviews_api.dart';
import 'package:alakh_service/features/services/data/datasources/service_remote_datasource.dart';
import 'package:alakh_service/features/services/data/models/service_model.dart';
import 'package:alakh_service/features/shops/data/saved_shops_api.dart';
import 'package:alakh_service/l10n/l10n.dart';
import 'package:alakh_service/shared/widgets/service_card.dart';
import 'package:alakh_service/shared/widgets/verified_badge.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

ApiClient clientWith(FakeHandler handler) => ApiClient(dio: fakeDio(FakeAdapter(handler)), tokens: MemoryTokenStore());

Map<String, dynamic> serviceJson({Map<String, dynamic> extra = const {}}) => {
      'id': 'svc1',
      'name': 'Fan repair',
      'price_cents': 29900,
      'shop_id': 'shop1',
      'duration_minutes': 30,
      ...extra,
    };

void main() {
  group('verified badge', () {
    testWidgets('a service card from a verified shop says so, in light and dark', (tester) async {
      for (final theme in [AppTheme.lightTheme, AppTheme.darkTheme]) {
        await tester.pumpWidget(MaterialApp(
          theme: theme,
          home: Scaffold(
            body: Column(children: [
              ServiceCard(service: ServiceModel.fromJson(serviceJson(extra: {'shop_is_verified': true}))),
              ServiceCard(service: ServiceModel.fromJson(serviceJson(extra: {'id': 'svc2', 'name': 'AC service'}))),
            ]),
          ),
        ));
        expect(find.text('Verified'), findsOneWidget);
        final icon = tester.widget<Icon>(find.descendant(of: find.byType(VerifiedBadge), matching: find.byType(Icon)));
        expect(icon.color, AppPalette.of(tester.element(find.byType(VerifiedBadge))).success);
      }
    });

    test('the badge comes from the listing, or from the shop ratings lookup', () async {
      final api = ServiceRemoteDataSourceImpl(
        apiClient: clientWith((r) => (status: 200, body: [serviceJson()])),
        ratings: ReviewsApi(clientWith((r) => (
              status: 200,
              body: [
                {'shop_id': 'shop1', 'average_rating': 4.5, 'review_count': 12, 'is_verified': true},
              ],
            ))),
      );
      final services = await api.getServices();
      expect(services.single.shopVerified, isTrue);
      expect(services.single.rating, 4.5);
      expect(ServiceModel.fromJson(serviceJson()).shopVerified, isFalse);
    });

    test('shops say whether they are verified', () async {
      final shop = await ShopLocationApi(clientWith((_) => (
            status: 200,
            body: {'id': 'shop1', 'name': 'Ravi Electricals', 'is_verified': true, 'verified_at': '2026-10-01T00:00:00Z'},
          ))).destination('shop1');
      expect(shop.isVerified, isTrue);
      expect(SavedShop.fromJson({'id': 's', 'name': 'S', 'is_verified': true}).isVerified, isTrue);
      expect(SavedShop.fromJson({'id': 's', 'name': 'S'}).isVerified, isFalse);
    });
  });

  testWidgets('a notification about a booking opens that booking', (tester) async {
    String? opened;
    final api = NotificationsApi(clientWith((r) => r.method == 'POST'
        ? (status: 200, body: {'updated': 1})
        : (
            status: 200,
            body: {
              'items': [
                {
                  'id': 'n1',
                  'title': 'Extra charges to approve',
                  'body': 'The shop asks for ₹500 more on BK-7',
                  'is_read': false,
                  'data': '{"event": "booking.extras_requested", "booking_id": "b7", "booking_number": "BK-7"}',
                  'created_at': DateTime.now().toUtc().toIso8601String(),
                },
              ],
            },
          )));
    await tester.pumpWidget(MaterialApp(
      home: NotificationsPage(notificationsApi: api, openBooking: (_, id) => opened = id),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Extra charges to approve'));
    await tester.pumpAndSettle();
    expect(opened, 'b7');
  });

  testWidgets('the new trust texts read in Hindi', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      locale: Locale('hi'),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      home: Scaffold(body: Column(children: [StartCodeCard(code: '4821'), VerifiedBadge()])),
    ));
    await tester.pumpAndSettle();
    expect(find.text('यह कोड तभी बताएँ जब प्रोफ़ेशनल आपके पास पहुँच जाए'), findsOneWidget);
    expect(find.text('सत्यापित'), findsOneWidget);
    final hi = lookupAppLocalizations(const Locale('hi'));
    expect(hi.extrasTitle, 'दुकान अतिरिक्त शुल्क माँग रही है');
    expect(hi.sosCall('112'), '112 पर कॉल करें');
  });
}
