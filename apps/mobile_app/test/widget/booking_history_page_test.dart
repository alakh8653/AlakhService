import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/network_info.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/rating_api.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/usecases/cancel_booking_usecase.dart';
import 'package:alakh_service/features/booking/domain/usecases/create_booking_usecase.dart';
import 'package:alakh_service/features/booking/presentation/bloc/booking_bloc.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_history_page.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

class Online implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

Map<String, dynamic> booking(String id, String status, String when, {int paise = 120000, String? shop = 'shop-1'}) => {
      'id': id,
      'booking_number': 'BK-$id',
      'customer_id': 'u1',
      'service_id': 's1',
      'shop_id': shop,
      'status': status,
      'scheduled_at': when,
      'total_amount': paise,
      'created_at': '2026-10-01T00:00:00Z',
    };

/// booking_service with the given bookings; cancelling answers [cancelStatus] and, when it
/// succeeds, marks the booking cancelled.
FakeAdapter server(List<Map<String, dynamic>> bookings, {int cancelStatus = 200, int rateStatus = 201}) {
  final items = [...bookings];
  return FakeAdapter((r) {
    if (r.path.endsWith('/payments')) return (status: 200, body: <Object>[]);
    if (r.path.endsWith('/rating')) return (status: rateStatus, body: {'detail': 'Already rated'});
    if (r.path.endsWith('/cancel')) {
      if (cancelStatus != 200) return (status: cancelStatus, body: {'detail': 'Too late to cancel this booking'});
      final id = r.path.split('/').reversed.elementAt(1);
      final i = items.indexWhere((b) => b['id'] == id);
      items[i] = {...items[i], 'status': 'CANCELLED'};
      return (status: 200, body: items[i]);
    }
    return (status: 200, body: {'items': items});
  });
}

Widget page(FakeAdapter adapter, {VoidCallback? onBrowse}) {
  final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
  final repo = BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online());
  return MaterialApp(
    home: BlocProvider(
      create: (_) => BookingBloc(
        createBookingUseCase: CreateBookingUseCase(repo),
        cancelBookingUseCase: CancelBookingUseCase(repo),
        bookingRepository: repo,
      ),
      child: BookingHistoryPage(
        onBrowseServices: onBrowse,
        paymentApi: PaymentApi(client),
        ratingApi: RatingApi(client),
      ),
    ),
  );
}

void main() {
  final future = DateTime.now().add(const Duration(days: 3)).toUtc().toIso8601String();
  final later = DateTime.now().add(const Duration(days: 9)).toUtc().toIso8601String();
  final past = DateTime.now().subtract(const Duration(days: 5)).toUtc().toIso8601String();

  testWidgets('splits bookings into upcoming (soonest first) and past, with Indian rupee formatting', (tester) async {
    await tester.pumpWidget(page(server([
      booking('done', 'COMPLETED', past),
      booking('later', 'CONFIRMED', later),
      booking('soon', 'PENDING', future, paise: 12000000),
    ])));
    await tester.pumpAndSettle();

    expect(find.text('Upcoming & active (2)'), findsOneWidget);
    expect(find.text('Past (1)'), findsOneWidget);
    final soon = tester.getTopLeft(find.text('Booking #BK-soon')).dy;
    final laterY = tester.getTopLeft(find.text('Booking #BK-later')).dy;
    final done = tester.getTopLeft(find.text('Booking #BK-done')).dy;
    expect(soon < laterY && laterY < done, isTrue);
    expect(find.text('₹1,20,000'), findsOneWidget); // lakh grouping
  });

  testWidgets('cancelling asks first, keeps the list on screen and confirms', (tester) async {
    final adapter = server([booking('b1', 'PENDING', future)]);
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Cancel booking'));
    await tester.pumpAndSettle();
    expect(find.text('Cancel this booking?'), findsOneWidget);
    await tester.tap(find.text('Keep booking'));
    await tester.pumpAndSettle();
    expect(adapter.requests.where((r) => r.path.endsWith('/cancel')), isEmpty);

    await tester.tap(find.text('Cancel booking'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Yes, cancel'));
    await tester.pumpAndSettle();

    expect(adapter.requests.where((r) => r.path.endsWith('/cancel')), hasLength(1));
    expect(find.text('Booking cancelled'), findsOneWidget);
    expect(find.text('Cancelled'), findsOneWidget); // reloaded, now under Past
    expect(find.text('Past (1)'), findsOneWidget);
  });

  testWidgets('a refused cancel shows why and leaves the list as it was', (tester) async {
    await tester.pumpWidget(page(server([booking('b1', 'CONFIRMED', future)], cancelStatus: 409)));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Cancel booking'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Yes, cancel'));
    await tester.pumpAndSettle();

    expect(find.text('Too late to cancel this booking'), findsOneWidget);
    expect(find.text('Booking #BK-b1'), findsOneWidget); // not replaced by an error screen
    expect(find.text('Cancel booking'), findsOneWidget); // can try again
  });

  testWidgets('an unconfirmed booking whose time has passed says so', (tester) async {
    final yesterday = DateTime.now().subtract(const Duration(days: 1)).toUtc().toIso8601String();
    await tester.pumpWidget(page(server([booking('old', 'PENDING', yesterday), booking('new', 'PENDING', future)])));
    await tester.pumpAndSettle();

    expect(find.textContaining("This time has passed and the shop hasn't confirmed"), findsOneWidget);
  });

  testWidgets('empty list explains and offers to browse services', (tester) async {
    var browsed = false;
    await tester.pumpWidget(page(server([]), onBrowse: () => browsed = true));
    await tester.pumpAndSettle();

    expect(find.text('No bookings yet'), findsOneWidget);
    await tester.tap(find.text('Browse services'));
    expect(browsed, isTrue);
  });

  testWidgets('a rated booking stops offering Rate', (tester) async {
    final adapter = server([booking('b1', 'COMPLETED', past)]);
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Rate'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('4 stars'));
    await tester.pump();
    expect(find.text('Good'), findsOneWidget);
    await tester.tap(find.text('Submit'));
    await tester.pumpAndSettle();

    expect(adapter.requests.where((r) => r.path.endsWith('/rating')).single.data, containsPair('rating', 4.0));
    expect(find.text('Rate'), findsNothing);
    expect(find.text('You rated it 4★'), findsOneWidget);
    expect(find.text('Thanks for rating!'), findsOneWidget);
    // Only stars were given, so no empty review is sent.
    expect(adapter.requests.where((r) => r.path.endsWith('/rating')).single.data, isNot(contains('comment')));
  });

  testWidgets('the rating sheet takes an optional written review and says thank you', (tester) async {
    final adapter = server([booking('b1', 'COMPLETED', past)]);
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Rate'));
    await tester.pumpAndSettle();
    expect(find.text('Shown with your first name and last initial'), findsOneWidget);
    await tester.enterText(find.widgetWithText(TextField, 'Write a review (optional)'), '  Neat cut, on time.  ');
    await tester.tap(find.text('Submit'));
    await tester.pumpAndSettle();

    final sent = adapter.requests.where((r) => r.path.endsWith('/rating')).single.data as Map;
    expect(sent, {'booking_id': 'b1', 'rating': 5.0, 'comment': 'Neat cut, on time.'});
    expect(find.text('Thanks for your review! It helps others choose.'), findsOneWidget);
    expect(find.text('You rated it 5★'), findsOneWidget);
  });
}
