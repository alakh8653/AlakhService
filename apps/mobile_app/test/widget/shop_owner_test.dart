import 'dart:typed_data';

import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/domain/entities/user.dart';
import 'package:alakh_service/features/shop_line/data/shop_line_api.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:alakh_service/shared/service_types.dart';
import 'package:alakh_service/features/shop_owner/presentation/owner_home_page.dart';
import 'package:alakh_service/features/shop_owner/presentation/shop_setup_page.dart';
import 'package:alakh_service/features/shop_owner/presentation/verification_page.dart';
import 'package:alakh_service/shared/widgets/custom_text_field.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../support/fake_adapter.dart';

final user = User(
  id: 'u1',
  name: 'Ravi Kumar',
  phone: '+919876543210',
  role: 'user',
  isVerified: true,
  createdAt: DateTime(2026),
);
const owned = OwnedShop('s1', 'Ravi Electricals', {'svc1': 'Fan repair'});

Map<String, Object?> shopJson({
  String status = 'APPROVED',
  String? submitted = '2026-11-01T00:00:00Z',
  String? reason,
  String? gstin,
}) =>
    {
      'id': 's1',
      'name': 'Ravi Electricals',
      'verification_status': status,
      'submitted_at': submitted,
      'rejection_reason': reason,
      'gstin': gstin,
    };

Map<String, Object?> bookingJson(String id, String status, {String mode = 'AT_SHOP', String name = 'Asha R.'}) => {
      'id': id,
      'booking_number': 'BK$id',
      'customer_display_name': name,
      'service_id': 'svc1',
      'status': status,
      'scheduled_at': '2026-11-03T06:00:00Z',
      'service_mode': mode,
      'total_amount': 29900,
    };

ShopOwnerApi apiWith(FakeAdapter adapter) => ShopOwnerApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));

Future<void> enter(WidgetTester tester, String label, String text) async {
  final field = find.descendant(
    of: find.ancestor(of: find.text(label), matching: find.byType(CustomTextField)),
    matching: find.byType(TextFormField),
  );
  await tester.ensureVisible(field);
  await tester.enterText(field, text);
}

Future<void> tapText(WidgetTester tester, String label) async {
  final target = find.text(label).last;
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('what the owner can do next', () {
    test('a new request is accepted or declined, however it is delivered', () {
      for (final mode in [modeAtShop, modeAtHome, modePickupDrop]) {
        expect(ownerActions('PENDING', mode), [OwnerAction.accept, OwnerAction.decline]);
      }
    });

    test('at the shop, the customer arrives; a home visit is taken, travelled to and started', () {
      expect(ownerActions('CONFIRMED', modeAtShop).first, OwnerAction.customerArrived);
      expect(ownerActions('CONFIRMED', modeAtHome).first, OwnerAction.goMyself);
      expect(ownerActions('ASSIGNED', modeAtHome).first, OwnerAction.onTheWay);
      expect(ownerActions('PROVIDER_EN_ROUTE', modeAtHome), [OwnerAction.start]);
      expect(ownerActions('IN_PROGRESS', modeAtHome), [OwnerAction.complete]);
    });

    test('nothing more can be done once a booking is finished', () {
      for (final status in ['COMPLETED', 'CANCELLED', 'REFUNDED', 'DISPUTED']) {
        expect(ownerActions(status, modeAtShop), isEmpty);
      }
    });
  });

  group('working hours', () {
    test('the chosen days get the hours, and the others are closed', () {
      final json = const WeekHours(days: {0, 6}, opens: 570, closes: 1110).toJson();
      final week = (json['weekly'] as List).cast<Map<String, Object?>>();
      expect(week, hasLength(7));
      expect(week[0]['intervals'], [
        {'start': '09:30', 'end': '18:30'},
      ]);
      expect(week[1]['intervals'], isEmpty);
    });

    test('a picked time goes to the nearest quarter hour, which is all the server takes', () {
      expect(WeekHours.toQuarterHour(10 * 60 + 7), 10 * 60);
      expect(WeekHours.toQuarterHour(10 * 60 + 8), 10 * 60 + 15);
      expect(WeekHours.toQuarterHour(10 * 60 + 30), 10 * 60 + 30);
      expect(WeekHours.hhmm(WeekHours.toQuarterHour(23 * 60 + 59)), '24:00');
    });

    test('a week with a lunch break is flagged rather than quietly flattened', () {
      Map<String, Object?> day(int d, List<List<String>> spans) => {
            'day': d,
            'intervals': [
              for (final span in spans) {'start': span[0], 'end': span[1]},
            ],
          };
      final hours = WeekHours.fromSchedule({
        'configured': true,
        'weekly': [
          day(0, [
            ['10:00', '13:00'],
            ['14:00', '20:00'],
          ]),
          day(1, []),
        ],
      });
      expect(hours.simplified, isTrue);
      expect(WeekHours.fromSchedule({'configured': false}).days, WeekHours.suggested.days);
    });
  });

  group('setting up a business', () {
    late FakeAdapter adapter;
    var failServicesOnce = false;

    setUp(() {
      failServicesOnce = false;
      adapter = FakeAdapter((RequestOptions r) {
        if (r.path.endsWith('/shops') && r.method == 'POST') {
          return (status: 201, body: shopJson(status: 'PENDING_REVIEW', submitted: null));
        }
        if (r.path.endsWith('/services') && r.method == 'POST') {
          if (failServicesOnce) {
            failServicesOnce = false;
            return (status: 500, body: {'detail': 'Try again'});
          }
          return (status: 201, body: {'id': 'svc1', 'name': 'Fan repair', 'price_cents': 25000});
        }
        if (r.path.endsWith('/staff') && r.method == 'GET') return (status: 200, body: <Object>[]);
        if (r.path.endsWith('/staff')) return (status: 201, body: {'id': 'st1'});
        if (r.path.endsWith('/hours')) return (status: 200, body: {'configured': true, 'weekly': []});
        if (r.path.endsWith('/documents')) return (status: 200, body: <Object>[]);
        if (r.path.endsWith('/verification-checklist')) return (status: 200, body: <Object>[]);
        if (r.path.endsWith('/payout-details')) return (status: 404, body: {'detail': 'No payout details yet'});
        return (status: 200, body: shopJson(status: 'PENDING_REVIEW', submitted: null));
      });
    });

    Future<void> pumpSetup(WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 12000);
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(MaterialApp(home: ShopSetupPage(user: user, api: apiWith(adapter))));
      await tester.pumpAndSettle();
    }

    Future<void> chooseCategory(WidgetTester tester) async {
      await tester.tap(find.byKey(const ValueKey('pick-type')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Electrical').last);
      await tester.pumpAndSettle();
    }

    Future<void> fillToLastStep(WidgetTester tester) async {
      await chooseCategory(tester);
      await tapText(tester, "At the customer's home");
      await enter(tester, 'City', 'Bengaluru');
      await tapText(tester, 'Continue');
      await tapText(tester, 'Fan repair');
      await enter(tester, 'Price', '250');
      await tapText(tester, 'Continue');
      expect(find.text('When do you work?'), findsOneWidget);
    }

    testWidgets('a person working alone goes from name to verification in three steps', (tester) async {
      await pumpSetup(tester);
      expect(find.text('Step 1 of 3'), findsOneWidget);
      // They need not have a shop: their own name is the suggestion.
      expect(find.text('Ravi Kumar'), findsOneWidget);
      await fillToLastStep(tester);
      await tapText(tester, 'Save and continue');

      final shop = adapter.requests.firstWhere((r) => r.path.endsWith('/shops') && r.method == 'POST');
      expect(shop.data['owner_id'], 'u1');
      expect(shop.data['city'], 'Bengaluru');
      expect(shop.data['category'], 'electrical');
      final service = adapter.requests.firstWhere((r) => r.path.endsWith('/services') && r.method == 'POST');
      // Rupees on screen, paise on the server.
      expect(service.data['price_cents'], 25000);
      expect(service.data['service_modes'], [modeAtHome]);
      final staff = adapter.requests.firstWhere((r) => r.path.endsWith('/staff') && r.method == 'POST');
      // A person alone must be on their own team, or their home visits cannot be assigned.
      expect(staff.data['user_id'], 'u1');
      expect(adapter.requests.any((r) => r.path.endsWith('/hours') && r.method == 'PUT'), isTrue);
      expect(find.text('Verification and payouts'), findsOneWidget);
    });

    testWidgets('type of work and place of work are chosen, never assumed', (tester) async {
      await pumpSetup(tester);
      await enter(tester, 'City', 'Pune');
      await tapText(tester, 'Continue');
      expect(find.text('Please fill this in'), findsOneWidget);
      expect(find.text('What do you offer?'), findsNothing);
      await chooseCategory(tester);
      await tapText(tester, 'Continue');
      expect(find.text('Choose at least one place you do the work.'), findsOneWidget);
      expect(find.text('What do you offer?'), findsNothing);
    });

    testWidgets('anyone finds their work by searching for what they do', (tester) async {
      await pumpSetup(tester);
      await tester.tap(find.byKey(const ValueKey('pick-type')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const ValueKey('search-type')), 'mason');
      await tester.pumpAndSettle();
      expect(find.text('Construction and masons'), findsOneWidget);
      expect(find.text('Electrical'), findsNothing);
      await tester.enterText(find.byKey(const ValueKey('search-type')), 'ac service');
      await tester.pumpAndSettle();
      await tester.tap(find.text('AC and appliance repair'));
      await tester.pumpAndSettle();
      expect(find.text('AC and appliance repair'), findsOneWidget);
    });

    testWidgets('select all, one price for all, and nothing has to be typed but the price', (tester) async {
      await pumpSetup(tester);
      await chooseCategory(tester);
      await tapText(tester, "At the customer's home");
      await enter(tester, 'City', 'Bengaluru');
      await tapText(tester, 'Continue');

      // Nothing chosen yet: it says so.
      await tapText(tester, 'Continue');
      expect(find.text('Choose at least one service.'), findsOneWidget);

      final count = serviceTypeById('electrical')!.suggestions.length;
      await tapText(tester, 'Select all');
      await enter(tester, 'Usual price for all (₹)', '300');
      await tapText(tester, 'Continue');
      await tapText(tester, 'Save and continue');
      final saved = adapter.requests.where((r) => r.path.endsWith('/services') && r.method == 'POST').toList();
      expect(saved, hasLength(count));
      expect(saved.every((r) => r.data['price_cents'] == 30000), isTrue);
      // Work at the customer's place starts at an hour.
      expect(saved.first.data['duration_minutes'], 60);
    });

    testWidgets('tapping a service again takes it off, and changing the work clears them', (tester) async {
      await pumpSetup(tester);
      await chooseCategory(tester);
      await tapText(tester, "At the customer's home");
      await enter(tester, 'City', 'Bengaluru');
      await tapText(tester, 'Continue');
      await tester.tap(find.widgetWithText(FilterChip, 'Fan repair'));
      await tester.pumpAndSettle();
      expect(find.byType(ServiceFields), findsOneWidget);
      await tester.tap(find.widgetWithText(FilterChip, 'Fan repair'));
      await tester.pumpAndSettle();
      expect(find.byType(ServiceFields), findsNothing);
    });

    testWidgets('a shop needs an address', (tester) async {
      await pumpSetup(tester);
      await chooseCategory(tester);
      await enter(tester, 'City', 'Pune');
      await tapText(tester, 'At my shop');
      await tapText(tester, 'Continue');
      expect(find.text('Please fill this in'), findsOneWidget);
    });

    testWidgets('trying again after a failure does not create a second shop', (tester) async {
      failServicesOnce = true;
      await pumpSetup(tester);
      await fillToLastStep(tester);
      await tapText(tester, 'Save and continue');
      expect(find.text('Try again'), findsOneWidget);
      await tapText(tester, 'Save and continue');
      expect(adapter.requests.where((r) => r.path.endsWith('/shops') && r.method == 'POST'), hasLength(1));
      expect(find.text('Verification and payouts'), findsOneWidget);
    });
  });

  group('verification', () {
    FakeAdapter verificationAdapter({
      List<Map<String, String>> documents = const [],
      Map<String, Object?>? shop,
      List<Map<String, Object>> checklist = const [],
    }) {
      final uploaded = [...documents];
      return FakeAdapter((RequestOptions r) {
        if (r.path.endsWith('/verification-checklist')) return (status: 200, body: checklist);
        if (r.path.endsWith('/documents/upload')) {
          uploaded.add({'type': r.queryParameters['type'] as String});
          return (status: 201, body: {'id': 'd1'});
        }
        if (r.path.endsWith('/documents')) return (status: 200, body: uploaded);
        if (r.path.endsWith('/payout-details') && r.method == 'GET') return (status: 404, body: {'detail': 'none'});
        if (r.path.endsWith('/payout-details')) return (status: 200, body: {'method': 'UPI'});
        return (status: 200, body: shop ?? shopJson(status: 'PENDING_REVIEW', submitted: null));
      });
    }

    Future<void> pump(WidgetTester tester, FakeAdapter adapter) async {
      tester.view.physicalSize = const Size(1200, 6000);
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: Center(
              child: TextButton(
                onPressed: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => VerificationPage(
                      shopId: 's1',
                      api: apiWith(adapter),
                      pickDocument: (_) async =>
                          PickedDocument(Uint8List.fromList([255, 216, 255]), 'image/jpeg', 'pan.jpg'),
                      pickPdf: () async => PickedDocument(Uint8List.fromList([37, 80, 68, 70]), 'application/pdf', 'cert.pdf'),
                    ),
                  ),
                ),
                child: const Text('open'),
              ),
            ),
          ),
        ),
      ));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
    }

    testWidgets('a PAN photo is required, and comes from the camera', (tester) async {
      final adapter = verificationAdapter();
      await pump(tester, adapter);
      await enter(tester, 'Name as on your PAN', 'Ravi Kumar');
      await tapText(tester, 'Submit for verification');
      // Beside the button and in a message that shows wherever they have scrolled to.
      expect(find.text('Please add a photo of your PAN card.'), findsNWidgets(2));
      expect(adapter.requests.any((r) => r.path.endsWith('/submit-for-review')), isFalse);

      // The message clears by itself and is not in the way afterwards.
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
      await tester.tap(find.descendant(of: find.byKey(const ValueKey('document-PAN')), matching: find.text('Add')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Take a photo'));
      await tester.pumpAndSettle();
      final upload = adapter.requests.firstWhere((r) => r.path.endsWith('/documents/upload'));
      expect(upload.queryParameters['type'], 'PAN');
      expect(upload.contentType, 'image/jpeg');

      await enter(tester, 'UPI ID', 'ravi@upi');
      await tapText(tester, 'Submit for verification');
      final legal = adapter.requests.firstWhere((r) => r.method == 'PUT' && r.path.endsWith('/shops/s1'));
      expect(legal.data['legal_name'], 'Ravi Kumar');
      final payout = adapter.requests.firstWhere((r) => r.method == 'PUT' && r.path.endsWith('/payout-details'));
      expect(payout.data['upi_id'], 'ravi@upi');
      expect(adapter.requests.any((r) => r.path.endsWith('/submit-for-review')), isTrue);
      // Nobody is left wondering whether it went.
      expect(find.text('Sent for verification'), findsOneWidget);
    });

    testWidgets('a doctor is asked for the council certificate, and it can be a PDF', (tester) async {
      final adapter = verificationAdapter(
        documents: [
          {'type': 'PAN'},
        ],
        checklist: [
          {
            'type': 'PROFESSIONAL_REGISTRATION',
            'label': 'Medical Council registration certificate',
            'required': true,
            'done': false,
          },
          {'type': 'WORK_PHOTO', 'label': 'Photos of your work', 'required': false, 'done': false},
        ],
      );
      await pump(tester, adapter);
      await enter(tester, 'Name as on your PAN', 'Dr Asha Rao');
      await enter(tester, 'UPI ID', 'asha@upi');
      await tapText(tester, 'Submit for verification');
      expect(find.text('Please add: Medical Council registration certificate'), findsNWidgets(2));
      expect(adapter.requests.any((r) => r.path.endsWith('/submit-for-review')), isFalse);

      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(of: find.byKey(const ValueKey('document-PROFESSIONAL_REGISTRATION')), matching: find.text('Add')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Choose a PDF file'));
      await tester.pumpAndSettle();
      final upload = adapter.requests.firstWhere((r) => r.path.endsWith('/documents/upload'));
      expect(upload.queryParameters['type'], 'PROFESSIONAL_REGISTRATION');
      expect(upload.contentType, 'application/pdf');

      await tapText(tester, 'Submit for verification');
      expect(adapter.requests.any((r) => r.path.endsWith('/submit-for-review')), isTrue);
    });

    testWidgets('what is left is listed at the top until it is done', (tester) async {
      final adapter = verificationAdapter();
      await pump(tester, adapter);
      expect(find.text('Before sending, you need:'), findsOneWidget);
      expect(find.byIcon(Icons.radio_button_unchecked), findsNWidgets(3));
      await enter(tester, 'Name as on your PAN', 'Ravi Kumar');
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.radio_button_unchecked), findsNWidgets(2));
    });

    testWidgets('giving a GSTIN asks for the certificate too', (tester) async {
      final adapter = verificationAdapter(documents: [
        {'type': 'PAN'},
      ]);
      await pump(tester, adapter);
      expect(find.byKey(const ValueKey('document-GST')), findsNothing);
      await enter(tester, 'Name as on your PAN', 'Ravi Kumar');
      await enter(tester, 'GSTIN (optional)', '27ABCDE1234F1Z5');
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('document-GST')), findsOneWidget);
      await tapText(tester, 'Submit for verification');
      expect(find.text('You gave a GSTIN, so please add a photo of your GST certificate.'), findsNWidgets(2));
    });

    testWidgets('a rejection says why and can be submitted again', (tester) async {
      final adapter = verificationAdapter(shop: shopJson(status: 'REJECTED', reason: 'PAN photo is blurred'));
      await pump(tester, adapter);
      expect(find.textContaining('PAN photo is blurred'), findsOneWidget);
      expect(find.text('Submit again'), findsOneWidget);
    });
  });

  group('owner home', () {
    late FakeAdapter adapter;
    late List<Map<String, Object?>> bookings;
    late Map<String, Object?> shop;
    late bool refuseActions;

    Future<void> pumpHome(WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 12000);
      addTearDown(tester.view.resetPhysicalSize);
      adapter = FakeAdapter((RequestOptions r) {
        if (refuseActions && r.path.endsWith('/status')) return (status: 409, body: {'detail': 'That slot is taken'});
        if (r.path.endsWith('/bookings/shop/s1')) {
          return (status: 200, body: {'items': bookings, 'total': bookings.length, 'page': 1, 'per_page': 100});
        }
        if (r.path.endsWith('/services')) {
          return (
            status: 200,
            body: [
              {'id': 'svc1', 'name': 'Fan repair', 'price_cents': 29900},
            ]
          );
        }
        if (r.path.endsWith('/staff') && r.method == 'GET') {
          return (
            status: 200,
            body: [
              {'id': 'st1', 'user_id': 'u1', 'is_active': true},
            ]
          );
        }
        if (r.path.endsWith('/shops/s1')) return (status: 200, body: shop);
        return (status: 200, body: <String, Object?>{});
      });
      await tester.pumpWidget(MaterialApp(
        home: OwnerHomePage(shop: owned, user: user, api: apiWith(adapter), refreshEvery: const Duration(hours: 1)),
      ));
      await tester.pumpAndSettle();
    }

    setUp(() {
      shop = shopJson();
      bookings = [];
      refuseActions = false;
    });

    testWidgets('every card says where the booking stands and whether it is paid', (tester) async {
      bookings = [
        {...bookingJson('b1', 'CONFIRMED', name: 'Paid P.'), 'payment_status': 'PAID'},
        bookingJson('b2', 'PENDING', name: 'New N.'),
      ];
      await pumpHome(tester);
      expect(find.text('Confirmed · Paid'), findsOneWidget);
      expect(find.text('Needs your answer · Not paid yet'), findsOneWidget);
    });

    testWidgets('a new request is accepted with one tap', (tester) async {
      bookings = [bookingJson('b1', 'PENDING')];
      await pumpHome(tester);
      expect(find.text('New requests (1)'), findsOneWidget);
      expect(find.text('Asha R.'), findsOneWidget);
      expect(find.text('Fan repair'), findsOneWidget);
      expect(find.textContaining('299'), findsOneWidget);
      await tester.tap(find.text('Accept'));
      await tester.pumpAndSettle();
      final put = adapter.requests.firstWhere((r) => r.method == 'PUT');
      expect(put.path, endsWith('/bookings/b1/status'));
      expect(put.data, {'status': 'CONFIRMED'});
    });

    testWidgets('declining asks first, says the customer is refunded, and sends a reason', (tester) async {
      bookings = [bookingJson('b1', 'PENDING')];
      await pumpHome(tester);
      await tester.tap(find.text('Decline'));
      await tester.pumpAndSettle();
      expect(find.text('The customer is told and gets back anything paid online.'), findsOneWidget);
      await tester.enterText(find.byType(TextField), 'Shop closed today');
      await tester.tap(find.widgetWithText(FilledButton, 'Decline'));
      await tester.pumpAndSettle();
      final post = adapter.requests.firstWhere((r) => r.path.endsWith('/bookings/b1/cancel'));
      expect(post.data, {'reason': 'Shop closed today'});
    });

    testWidgets('backing out of declining changes nothing', (tester) async {
      bookings = [bookingJson('b1', 'PENDING')];
      await pumpHome(tester);
      await tester.tap(find.text('Decline'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Not now'));
      await tester.pumpAndSettle();
      expect(adapter.requests.any((r) => r.path.endsWith('/cancel')), isFalse);
    });

    testWidgets('a person alone takes their own home visit', (tester) async {
      bookings = [bookingJson('b1', 'CONFIRMED', mode: modeAtHome)];
      await pumpHome(tester);
      expect(find.text('Home visit'), findsOneWidget);
      await tester.tap(find.text('I will do this job'));
      await tester.pumpAndSettle();
      final assign = adapter.requests.firstWhere((r) => r.path.endsWith('/bookings/b1/assign'));
      expect(assign.data, {'provider_id': 'u1'});
    });

    testWidgets('finished bookings leave the list', (tester) async {
      bookings = [bookingJson('b1', 'COMPLETED', name: 'Done D.'), bookingJson('b2', 'CANCELLED', name: 'Gone G.')];
      await pumpHome(tester);
      expect(find.text('Done D.'), findsNothing);
      expect(find.text('Gone G.'), findsNothing);
      expect(find.text('Nothing booked yet.'), findsOneWidget);
    });

    testWidgets('until approved, the owner is told what is holding them back', (tester) async {
      shop = shopJson(status: 'PENDING_REVIEW', submitted: null);
      await pumpHome(tester);
      expect(find.text('Finish verification so customers can book you'), findsOneWidget);
    });

    testWidgets('no banner once approved', (tester) async {
      await pumpHome(tester);
      expect(find.byKey(const ValueKey('owner-banner')), findsNothing);
    });

    testWidgets('when the server refuses, the owner sees why and the request stays', (tester) async {
      bookings = [bookingJson('b1', 'PENDING')];
      refuseActions = true;
      await pumpHome(tester);
      await tester.tap(find.text('Accept'));
      await tester.pumpAndSettle();
      expect(find.text('That slot is taken'), findsOneWidget);
      expect(find.text('Accept'), findsOneWidget);
    });
  });
}
