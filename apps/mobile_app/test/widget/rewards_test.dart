import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/usecases/cancel_booking_usecase.dart';
import 'package:alakh_service/features/booking/domain/usecases/create_booking_usecase.dart';
import 'package:alakh_service/features/booking/presentation/bloc/booking_bloc.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_page.dart';
import 'package:alakh_service/features/loyalty/data/loyalty_api.dart';
import 'package:alakh_service/features/loyalty/presentation/rewards_page.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_page_test.dart' as booking_page show Online, now, pickDateAndTime, server;

Map<String, Object?> summary({int points = 120, bool referred = false}) => {
      'points': points,
      'value_cents': points * 100,
      'point_value_cents': 100,
      'points_per_100_rupees': 2,
      'redeem_max_percent': 20,
      'referral_code': 'ALK7Q2XZ',
      'referral_bonus_points': 100,
      'friends_rewarded': 1,
      'friends_pending': 2,
      'referred_by_friend': referred,
      'history': [
        {'kind': 'REFERRAL_BONUS', 'points': 100, 'booking_id': 'b1', 'note': null, 'created_at': '2026-10-20T10:00:00Z'},
        {'kind': 'EARN', 'points': 20, 'booking_id': 'b1', 'note': null, 'created_at': '2026-10-20T10:00:00Z'},
      ],
    };

ApiClient clientFor(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

void main() {
  test('points pay up to the share of the price they may, in whole points', () {
    final s = LoyaltySummary.fromJson(summary(points: 120));
    expect(s.discountOn(300), 60); // 20% of ₹300
    expect(s.discountOn(1000), 120); // all the points
    expect(s.discountOn(49.5), 9); // ₹9.90 rounds down to whole points
  });

  testWidgets('rewards show the points, the code to share, and take a friend\'s code', (tester) async {
    final adapter = FakeAdapter((r) => r.path.endsWith('/loyalty/referral')
        ? (status: 201, body: {'message': 'Code added. You both get 100 points after your first booking.'})
        : (status: 200, body: summary()));
    final opened = <Uri>[];
    await tester.pumpWidget(MaterialApp(
      home: RewardsPage(api: LoyaltyApi(clientFor(adapter)), openLink: (uri) async {
        opened.add(uri);
        return true;
      }),
    ));
    await tester.pumpAndSettle();

    expect(find.text('120 points'), findsOneWidget);
    expect(find.text('Worth ₹120 on your next bookings'), findsOneWidget);
    expect(find.text('ALK7Q2XZ'), findsOneWidget);
    expect(find.text('1 friends booked · 2 yet to book'), findsOneWidget);
    expect(find.text('Referral bonus'), findsOneWidget);
    expect(find.text('+100'), findsOneWidget);

    await tester.tap(find.byTooltip('Share on WhatsApp'));
    await tester.pump();
    expect(opened.single.host, 'wa.me');
    expect(opened.single.queryParameters['text'], contains('ALK7Q2XZ'));

    await tester.ensureVisible(find.byType(TextField));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'frnd1234');
    await tester.tap(find.text('Apply'));
    await tester.pumpAndSettle();
    final sent = adapter.requests.singleWhere((r) => r.path.endsWith('/loyalty/referral'));
    expect((sent.data as Map)['code'], 'frnd1234');
    expect(find.text('Code added. You both get 100 points after your first booking.'), findsOneWidget);
  });

  testWidgets('someone who joined with a code is not asked for one', (tester) async {
    final adapter = FakeAdapter((r) => (status: 200, body: summary(referred: true)));
    await tester.pumpWidget(MaterialApp(home: RewardsPage(api: LoyaltyApi(clientFor(adapter)))));
    await tester.pumpAndSettle();
    expect(find.text("Got a friend's code?"), findsNothing);
  });

  testWidgets('booking can use points, shown in the price and sent with the booking', (tester) async {
    final base = booking_page.server();
    final adapter = FakeAdapter((r) => r.path.endsWith('/loyalty/me') ? (status: 200, body: summary(points: 500)) : base.handler(r));
    final client = clientFor(adapter);
    final repo = BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: booking_page.Online());
    await tester.pumpWidget(MaterialApp(
      home: BlocProvider(
        create: (_) => BookingBloc(
          createBookingUseCase: CreateBookingUseCase(repo),
          cancelBookingUseCase: CancelBookingUseCase(repo),
          bookingRepository: repo,
        ),
        child: BookingPage(
          serviceId: 's1',
          serviceName: 'Haircut',
          servicePrice: 300,
          addressApi: AddressApi(client),
          availabilityApi: AvailabilityApi(client),
          loyaltyApi: LoyaltyApi(client),
          clock: booking_page.now,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Save ₹60 · 500 points available'), findsOneWidget);
    await tester.ensureVisible(find.text('Use my points'));
    await tester.tap(find.text('Use my points'));
    await tester.pumpAndSettle();
    expect(find.text('−₹60'), findsOneWidget);
    expect(find.text('₹240'), findsWidgets); // the total

    await booking_page.pickDateAndTime(tester);
    await tester.tap(find.text('Confirm Booking'));
    await tester.pumpAndSettle();
    final sent = adapter.requests.singleWhere((r) => r.method == 'POST' && r.path.endsWith('/bookings'));
    expect((sent.data as Map)['use_points'], isTrue);
  });
}
