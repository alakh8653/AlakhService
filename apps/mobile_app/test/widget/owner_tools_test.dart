import 'package:alakh_service/app/app_links.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/reviews/data/reviews_api.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:alakh_service/features/shop_owner/presentation/owner_tools_pages.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

ApiClient client(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

Future<void> pump(WidgetTester tester, Widget page) async {
  await tester.pumpWidget(MaterialApp(home: page));
  await tester.pumpAndSettle();
}

void main() {
  group('days off', () {
    late List<String> holidays;
    late FakeAdapter adapter;

    setUp(() {
      holidays = ['2026-11-20'];
      adapter = FakeAdapter((RequestOptions r) {
        if (r.method == 'POST') {
          holidays.add(r.data['date'] as String);
          return (status: 201, body: <String, Object?>{});
        }
        if (r.method == 'DELETE') {
          holidays.remove(r.path.split('/').last);
          return (status: 204, body: null);
        }
        return (
          status: 200,
          body: {
            'holidays': [
              for (final day in holidays) {'date': day},
            ],
          },
        );
      });
    });

    Widget page() => OwnerDaysOffPage(
          shopId: 's1',
          api: ShopOwnerApi(client(adapter)),
          now: () => DateTime(2026, 11, 3),
        );

    testWidgets('today and tomorrow take one tap, and a day off can be taken back', (tester) async {
      await pump(tester, page());
      expect(find.text('Fri, 20 Nov 2026'), findsOneWidget);

      await tester.tap(find.text('Off today'));
      await tester.pumpAndSettle();
      expect(holidays, contains('2026-11-03'));
      await tester.tap(find.text('Off tomorrow'));
      await tester.pumpAndSettle();
      expect(holidays, contains('2026-11-04'));
      expect(find.text('Wed, 4 Nov 2026'), findsOneWidget);

      await tester.tap(find.widgetWithText(TextButton, 'Remove').first);
      await tester.pumpAndSettle();
      expect(holidays, hasLength(2));
    });

    testWidgets('it warns that bookings already made stay', (tester) async {
      await pump(tester, page());
      expect(find.textContaining('Bookings you already have stay'), findsOneWidget);
    });

    testWidgets('the server refusing is shown', (tester) async {
      final refusing = FakeAdapter((RequestOptions r) {
        if (r.method == 'POST') return (status: 409, body: {'detail': '2026-11-03 is already a holiday'});
        return (status: 200, body: {'holidays': <Object>[]});
      });
      await pump(tester, OwnerDaysOffPage(shopId: 's1', api: ShopOwnerApi(client(refusing)), now: () => DateTime(2026, 11, 3)));
      await tester.tap(find.text('Off today'));
      await tester.pumpAndSettle();
      expect(find.text('2026-11-03 is already a holiday'), findsOneWidget);
    });
  });

  group('reviews', () {
    testWidgets('the owner replies, and the reply shows', (tester) async {
      Map<String, Object?>? reply;
      final adapter = FakeAdapter((RequestOptions r) {
        if (r.method == 'PUT') {
          reply = {'text': r.data['text'], 'updated_at': '2026-11-03T06:00:00Z'};
          return (status: 200, body: <String, Object?>{});
        }
        return (
          status: 200,
          body: {
            'total': 1,
            'items': [
              {'id': 'r1', 'rating': 4, 'comment': 'Good work', 'reviewer_name': 'Asha R.', 'created_at': '2026-11-01T06:00:00Z', 'reply': reply},
            ],
          },
        );
      });
      final api = client(adapter);
      await pump(tester, OwnerReviewsPage(shopId: 's1', api: ShopOwnerApi(api), reviews: ReviewsApi(api)));
      expect(find.text('Good work'), findsOneWidget);

      await tester.tap(find.text('Reply'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'Thank you, Asha');
      await tester.tap(find.widgetWithText(FilledButton, 'Save'));
      await tester.pumpAndSettle();
      expect(adapter.requests.last.method, 'GET');
      expect(find.textContaining('Thank you, Asha'), findsOneWidget);
      expect(find.text('Edit reply'), findsOneWidget);
    });
  });

  group('customers', () {
    testWidgets('names, visits and who came back, with no phone number', (tester) async {
      final adapter = FakeAdapter((RequestOptions r) => (
            status: 200,
            body: [
              {'name': 'Asha R.', 'visits': 3, 'spent': 1500, 'last_visit': '2026-11-02T06:00:00Z'},
              {'name': 'Ravi S.', 'visits': 1, 'spent': 300, 'last_visit': '2026-10-20T06:00:00Z'},
            ],
          ));
      await pump(tester, OwnerCustomersPage(shopId: 's1', api: ShopOwnerApi(client(adapter))));
      expect(find.text('2 customers, 1 came back'), findsOneWidget);
      expect(find.text('Asha R.'), findsOneWidget);
      expect(find.text('3 visits, last on Mon, 2 Nov 2026'), findsOneWidget);
      expect(find.text('₹1,500'), findsOneWidget);
    });
  });

  group('share', () {
    OwnerShop shopWith(String status) => OwnerShop.fromJson({
          'id': 's1',
          'name': 'Ravi Electricals',
          'owner_id': 'u1',
          'category': 'electrical',
          'verification_status': status,
        });

    testWidgets('it opens WhatsApp with the shop link in the message', (tester) async {
      Uri? opened;
      await pump(
        tester,
        OwnerSharePage(
          shop: shopWith('APPROVED'),
          open: (uri) async {
            opened = uri;
            return true;
          },
        ),
      );
      await tester.tap(find.text('Share on WhatsApp'));
      await tester.pumpAndSettle();
      expect(opened!.host, 'wa.me');
      expect(opened!.queryParameters['text'], contains('Ravi Electricals'));
      expect(opened!.queryParameters['text'], contains('https://$appLinkDomain/s/s1'));
    });

    testWidgets('it says so when WhatsApp cannot be opened', (tester) async {
      await pump(tester, OwnerSharePage(shop: shopWith('APPROVED'), open: (_) async => false));
      await tester.tap(find.text('Share on WhatsApp'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Could not open WhatsApp'), findsOneWidget);
    });

    testWidgets('a shop not approved yet has no link to give out', (tester) async {
      await pump(tester, OwnerSharePage(shop: shopWith('PENDING_REVIEW')));
      expect(find.text('Share on WhatsApp'), findsNothing);
      expect(find.textContaining('once your business is approved'), findsOneWidget);
    });
  });

  test('a shared link opens the shop', () {
    expect(parseAppLink(Uri.parse('https://$appLinkDomain/s/abc123')), const ShopTarget('abc123'));
    expect(parseAppLink(Uri.parse('https://$appLinkDomain/s/abc/extra')), isNull);
    expect(parseAppLink(Uri.parse('https://evil.example/s/abc123')), isNull);
  });
}
