import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/models/booking_model.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/entities/booking.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_details_page.dart';
import 'package:alakh_service/features/booking/presentation/pages/reschedule_page.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/directions/data/shop_location_api.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/queue/data/queue_api.dart';
import 'package:alakh_service/features/reviews/data/reviews_api.dart';
import 'package:alakh_service/features/services/domain/entities/service_entity.dart';
import 'package:alakh_service/features/services/presentation/pages/service_detail_page.dart';
import 'package:alakh_service/features/shops/data/saved_shops_api.dart';
import 'package:alakh_service/features/shops/data/shop_hours_api.dart';
import 'package:alakh_service/features/shops/presentation/saved_shops_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_history_page_test.dart' show Online, booking;

ApiClient clientFor(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

BookingRepositoryImpl repoFor(ApiClient client) =>
    BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online());

/// 9 AM on Sunday 18 Oct 2026 (India), the booking at 11 AM on Monday 19 Oct.
DateTime now() => DateTime(2026, 10, 18, 9);
const bookedAt = '2026-10-19T05:30:00Z';

void main() {
  group('when a booking can be moved or booked again', () {
    Booking b(String status, {int moves = 0, DateTime? at}) => BookingModel.fromJson({
          ...booking('b', status, (at ?? DateTime.utc(2026, 10, 19, 5, 30)).toIso8601String()),
          'reschedule_count': moves,
        });

    test('a pending or confirmed booking, more than 2 hours ahead, moved fewer than twice', () {
      expect(b('PENDING').canReschedule(now()), isTrue);
      expect(b('CONFIRMED', moves: 1).canReschedule(now()), isTrue);
      expect(b('CONFIRMED', moves: 2).canReschedule(now()), isFalse);
      expect(b('ASSIGNED').canReschedule(now()), isFalse);
      final soon = DateTime.now().toUtc().add(const Duration(minutes: 90));
      expect(b('CONFIRMED', at: soon).canReschedule(DateTime.now()), isFalse);
    });

    test('a finished booking can be booked again; an active one cannot', () {
      expect(b('COMPLETED').canBookAgain, isTrue);
      expect(b('CANCELLED').canBookAgain, isTrue);
      expect(b('CONFIRMED').canBookAgain, isFalse);
    });
  });

  testWidgets('moving a booking offers free times without its own and sends the new one', (tester) async {
    final adapter = FakeAdapter((r) {
      if (r.path.endsWith('/availability')) {
        return (status: 200, body: {
          'hours_configured': true,
          'status': 'AVAILABLE',
          'slots': [
            {'start': bookedAt, 'time': '11:00', 'remaining': 1}, // its current time: not offered
            {'start': '2026-10-18T07:30:00Z', 'time': '13:00', 'remaining': 1},
          ],
        });
      }
      return (status: 200, body: {...booking('b1', 'CONFIRMED', '2026-10-18T07:30:00Z'), 'reschedule_count': 1});
    });
    final client = clientFor(adapter);
    final current = BookingModel.fromJson(booking('b1', 'CONFIRMED', bookedAt));
    Booking? popped;
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => TextButton(
          onPressed: () async => popped = await Navigator.push<Booking>(
            context,
            MaterialPageRoute(
              builder: (_) => ReschedulePage(booking: current, repository: repoFor(client), availabilityApi: AvailabilityApi(client), clock: now),
            ),
          ),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    final asked = adapter.requests.firstWhere((r) => r.path.endsWith('/availability'));
    expect(asked.queryParameters['moving_booking_id'], 'b1');
    expect(find.text('11:00 AM'), findsNothing);
    expect(find.text('1:00 PM'), findsOneWidget);
    expect(find.textContaining('Changes left: 2'), findsOneWidget);
    final confirm = find.widgetWithText(FilledButton, 'Confirm new time');
    expect(tester.widget<FilledButton>(confirm).onPressed, isNull); // nothing picked yet

    await tester.tap(find.text('1:00 PM'));
    await tester.pumpAndSettle();
    await tester.tap(confirm);
    await tester.pumpAndSettle();

    final sent = adapter.requests.singleWhere((r) => r.path.endsWith('/bookings/b1/reschedule'));
    expect(sent.method, 'POST');
    expect((sent.data as Map)['scheduled_at'], '2026-10-18T07:30:00.000Z');
    expect(popped?.rescheduleCount, 1);
  });

  testWidgets('booking details offer Change time ahead of time and Book again once it is over', (tester) async {
    Widget details(Map<String, dynamic> b) {
      final client = clientFor(FakeAdapter((r) => r.path.endsWith('/payments')
          ? (status: 200, body: <Object>[])
          : r.path.endsWith('/messages')
          ? (status: 200, body: {'items': <Object>[], 'total': 0, 'page': 1, 'per_page': 1, 'unread': 0, 'can_send': true, 'calling_enabled': false})
          : (status: 200, body: b)));
      return MaterialApp(
        home: BookingDetailsPage(
          key: ValueKey(b['id']), // a new page for each booking, not the last one's state
          bookingId: b['id'] as String,
          repository: repoFor(client),
          paymentApi: PaymentApi(client),
          chatApi: ChatApi(client),
          clock: now,
        ),
      );
    }

    await tester.pumpWidget(details(booking('b1', 'CONFIRMED', bookedAt)));
    await tester.pumpAndSettle();
    expect(find.text('Change time'), findsOneWidget);
    expect(find.text('Book again'), findsNothing);

    await tester.pumpWidget(details(booking('b2', 'COMPLETED', '2026-10-10T05:30:00Z')));
    await tester.pumpAndSettle();
    expect(find.text('Change time'), findsNothing);
    expect(find.text('Book again'), findsOneWidget);
  });

  testWidgets('saved shops are listed, open their services, and can be removed', (tester) async {
    final adapter = FakeAdapter((r) {
      if (r.path.endsWith('/shops/favorites')) {
        return (status: 200, body: [
          {'id': 'shop-1', 'name': 'Demo Salon', 'category': 'salon', 'city': 'Pune', 'rating_avg': 4.5, 'rating_count': 12},
        ]);
      }
      if (r.path.endsWith('/services')) {
        return (status: 200, body: [
          {'id': 's1', 'name': 'Haircut', 'shop_id': 'shop-1', 'price_cents': 30000, 'duration_minutes': 30, 'is_active': true},
          {'id': 's2', 'name': 'Old offer', 'shop_id': 'shop-1', 'price_cents': 100, 'is_active': false},
        ]);
      }
      return (status: 204, body: null);
    });
    final api = SavedShopsApi(clientFor(adapter));
    await tester.pumpWidget(MaterialApp(home: SavedShopsPage(api: api)));
    await tester.pumpAndSettle();

    expect(find.text('Demo Salon'), findsOneWidget);
    expect(find.text('salon · Pune · ★ 4.5 (12)'), findsOneWidget);

    await tester.tap(find.text('Demo Salon'));
    await tester.pumpAndSettle();
    expect(find.text('Haircut'), findsOneWidget);
    expect(find.text('Old offer'), findsNothing);
    expect(adapter.requests.last.queryParameters['shop_id'], 'shop-1');

    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Remove from saved shops'));
    await tester.pumpAndSettle();
    expect(adapter.requests.last.method, 'DELETE');
    expect(adapter.requests.last.path, endsWith('/shops/shop-1/favorite'));
    expect(find.text('Demo Salon'), findsNothing);
    expect(find.textContaining('No saved shops yet'), findsOneWidget);
  });

  testWidgets('the heart on a service saves its shop', (tester) async {
    final adapter = FakeAdapter((r) => r.path.endsWith('/shops/favorites')
        ? (status: 200, body: <Object>[])
        : r.path.endsWith('/favorite')
        ? (status: 204, body: null)
        : r.path.contains('/shops/') && !r.path.contains('/reviews') && !r.path.endsWith('/hours')
        ? (status: 200, body: {'name': 'Demo Salon', 'address': '12 MG Road', 'city': 'Pune'})
        : (status: 200, body: <Object>[]));
    final client = clientFor(adapter);
    const service = ServiceEntity(
      id: 's1', name: 'Haircut', description: '', category: '', basePrice: 300, priceUnit: '30 min', shopId: 'shop-1',
    );
    await tester.pumpWidget(MaterialApp(
      home: ServiceDetailPage(
        service: service,
        shopApi: ShopLocationApi(client),
        queueApi: QueueApi(client),
        reviewsApi: ReviewsApi(client),
        hoursApi: ShopHoursApi(client),
        savedShopsApi: SavedShopsApi(client),
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Save shop'));
    await tester.pumpAndSettle();
    final put = adapter.requests.singleWhere((r) => r.path.endsWith('/shops/shop-1/favorite'));
    expect(put.method, 'PUT');
    expect(find.byTooltip('Remove from saved shops'), findsOneWidget);
    expect(find.text('Shop saved'), findsOneWidget);
  });
}
