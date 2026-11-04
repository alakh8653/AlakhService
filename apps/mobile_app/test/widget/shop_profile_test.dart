import 'dart:typed_data';

import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:alakh_service/features/shop_owner/presentation/owner_profile_page.dart';
import 'package:alakh_service/features/shops/data/shop_profile_api.dart';
import 'package:alakh_service/features/shops/presentation/shop_profile_section.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

void main() {
  late Map<String, Object?> shop;
  late List<Map<String, Object?>> photos;
  late FakeAdapter adapter;
  var failing = false;

  setUp(() {
    failing = false;
    shop = {'id': 's1', 'name': 'Ravi', 'description': 'AC work since 2015', 'years_experience': 9, 'languages': ['Hindi', 'Tamil']};
    photos = [
      {'id': 'p1', 'url': '/api/v1/shops/s1/photos/p1/file', 'caption': 'New wiring'},
    ];
    adapter = FakeAdapter((RequestOptions r) {
      if (failing) return (status: 500, body: {'detail': 'Please try again'});
      if (r.path.endsWith('/report')) return (status: 202, body: {'status': 'reported'});
      if (r.path.endsWith('/photos') && r.method == 'POST') {
        photos.add({'id': 'p2', 'url': '/api/v1/shops/s1/photos/p2/file'});
        return (status: 201, body: photos.last);
      }
      if (r.path.endsWith('/photos')) return (status: 200, body: photos);
      if (r.path.contains('/photos/') && r.method == 'DELETE') {
        photos.removeWhere((p) => r.path.endsWith(p['id'] as String));
        return (status: 204, body: null);
      }
      if (r.method == 'PUT') {
        shop = {...shop, ...(r.data as Map<String, dynamic>)};
        return (status: 200, body: shop);
      }
      return (status: 200, body: shop);
    });
  });

  ApiClient client() => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

  group('the customer', () {
    Future<void> pump(WidgetTester tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: ListView(children: [ShopProfileSection(shopId: 's1', api: ShopProfileApi(client()))])),
      ));
      await tester.pumpAndSettle();
    }

    testWidgets('sees experience, languages, the words and the photos', (tester) async {
      await pump(tester);
      expect(find.text('9 years of experience'), findsOneWidget);
      expect(find.text('Hindi, Tamil'), findsOneWidget);
      expect(find.text('AC work since 2015'), findsOneWidget);
      expect(find.byKey(const ValueKey('work-photo-p1')), findsOneWidget);
    });

    testWidgets('a photo can be reported from the full view, with a reason to tap', (tester) async {
      await pump(tester);
      await tester.tap(find.byKey(const ValueKey('work-photo-p1')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('report-photo')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('It is offensive'));
      await tester.pumpAndSettle();
      final sent = adapter.requests.firstWhere((r) => r.path.endsWith('/photos/p1/report'));
      expect(sent.data['reason'], 'It is offensive');
      expect(find.text('Thanks. We will check this photo.'), findsOneWidget);
    });

    testWidgets('backing out of reporting sends nothing', (tester) async {
      await pump(tester);
      await tester.tap(find.byKey(const ValueKey('work-photo-p1')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('report-photo')));
      await tester.pumpAndSettle();
      await tester.tapAt(const Offset(5, 5));
      await tester.pumpAndSettle();
      expect(adapter.requests.any((r) => r.path.endsWith('/report')), isFalse);
    });

    testWidgets('a business with nothing added shows nothing, not an empty box', (tester) async {
      shop = {'id': 's1', 'name': 'Ravi'};
      photos = [];
      await pump(tester);
      expect(find.text('About this provider'), findsNothing);
    });

    testWidgets('a profile that fails to load stays out of the way', (tester) async {
      failing = true;
      await pump(tester);
      expect(find.text('About this provider'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  });

  group('the owner', () {
    Future<void> pump(WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 4000);
      addTearDown(tester.view.resetPhysicalSize);
      final api = client();
      await tester.pumpWidget(MaterialApp(
        home: OwnerProfilePage(
          shopId: 's1',
          api: ShopOwnerApi(api),
          profileApi: ShopProfileApi(api),
          pickPhoto: (_) async => PickedDocument(Uint8List.fromList([255, 216, 255]), 'image/jpeg', 'work.jpg'),
        ),
      ));
      await tester.pumpAndSettle();
    }

    testWidgets('finds what they saved, and changes it with taps and a number', (tester) async {
      await pump(tester);
      expect(find.text('AC work since 2015'), findsOneWidget);
      await tester.enterText(find.byKey(const ValueKey('profile-years')), '12');
      await tester.tap(find.text('Punjabi'));
      await tester.pump();
      await tester.tap(find.text('Tamil'));
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Save'));
      await tester.pumpAndSettle();
      final sent = adapter.requests.firstWhere((r) => r.method == 'PUT');
      expect(sent.data['years_experience'], 12);
      expect(sent.data['languages'], unorderedEquals(['Hindi', 'Punjabi']));
      expect(sent.data['description'], 'AC work since 2015');
      expect(find.text('Saved. Customers can see this.'), findsOneWidget);
    });

    testWidgets('adds a photo from the camera and removes one', (tester) async {
      await pump(tester);
      await tester.tap(find.text('Add a photo'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Take a photo'));
      await tester.pumpAndSettle();
      final upload = adapter.requests.firstWhere((r) => r.path.endsWith('/photos') && r.method == 'POST');
      expect(upload.contentType, 'image/jpeg');
      expect(photos, hasLength(2));

      await tester.tap(find.byKey(const ValueKey('remove-photo-p1')));
      await tester.pumpAndSettle();
      expect(photos.map((p) => p['id']), ['p2']);
    });

    testWidgets('a hidden photo is marked, so they know why customers cannot see it', (tester) async {
      photos = [
        {'id': 'p1', 'url': '/api/v1/shops/s1/photos/p1/file', 'is_hidden': true},
      ];
      await pump(tester);
      expect(find.text('Hidden while we check'), findsOneWidget);
    });

    testWidgets('the server refusing is shown', (tester) async {
      await pump(tester);
      failing = true;
      await tester.tap(find.widgetWithText(FilledButton, 'Save'));
      await tester.pumpAndSettle();
      expect(find.text('Please try again'), findsOneWidget);
    });
  });
}
