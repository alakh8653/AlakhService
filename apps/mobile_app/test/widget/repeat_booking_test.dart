import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repeat_booking.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/entities/booking.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_details_page.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_history_page_test.dart' show Online, booking;

final now = DateTime(2026, 12, 1, 9);
// The original visit: Wednesday 2 Dec, 10:30 local.
final original = DateTime(2026, 12, 2, 10, 30);

/// booking_service and its availability: [fullOn] days have no place at 10:30; [refuse] days are refused when
/// booked. Booking requests (and their keys) are recorded.
class Shop {
  final Set<int> fullOn;
  final Set<int> refuse;
  final booked = <RequestOptions>[];

  Shop({this.fullOn = const {}, this.refuse = const {}});

  late final adapter = FakeAdapter((r) {
    if (r.path.endsWith('/availability')) {
      final day = DateTime.parse(r.queryParameters['date'] as String);
      final at = DateTime(day.year, day.month, day.day, 10, 30).toUtc();
      return (
        status: 200,
        body: {
          'hours_configured': true,
          'status': fullOn.contains(day.day) ? 'FULLY_BOOKED' : 'OPEN',
          'slots': [
            if (!fullOn.contains(day.day)) {'at': at.toIso8601String(), 'time': '10:30'},
          ],
        },
      );
    }
    if (r.method == 'POST' && r.path.endsWith('/bookings')) {
      booked.add(r);
      final at = DateTime.parse((r.data as Map)['scheduled_at'] as String).toLocal();
      if (refuse.contains(at.day)) return (status: 409, body: {'detail': 'The shop is fully booked then'});
      return (status: 201, body: booking('n${booked.length}', 'PENDING', (r.data as Map)['scheduled_at'] as String));
    }
    if (r.path.endsWith('/payments')) return (status: 200, body: <Object>[]);
    if (r.path.endsWith('/messages')) {
      return (status: 200, body: {'items': <Object>[], 'total': 0, 'page': 1, 'per_page': 1, 'unread': 0, 'can_send': true});
    }
    return (status: 200, body: booking('b1', 'COMPLETED', original.toUtc().toIso8601String()));
  });

  ApiClient get client => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

  RepeatBooker booker() => RepeatBooker(
        bookings: BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online()),
        availability: AvailabilityApi(client),
        now: () => now,
      );
}

Booking visit() => Booking(
      id: 'b1',
      bookingNumber: 'BK-1',
      userId: 'u1',
      serviceId: 's1',
      serviceName: 'Haircut',
      status: BookingStatus.completed,
      scheduledAt: original,
      durationMinutes: 30,
      address: '',
      totalAmount: 300,
      createdAt: now,
    );

void main() {
  test('dates fall on the same weekday and time, and only in the future', () {
    final dates = Shop().booker().datesFor(visit(), 2, 3);
    expect(dates, [DateTime(2026, 12, 16, 10, 30), DateTime(2026, 12, 30, 10, 30), DateTime(2027, 1, 13, 10, 30)]);
    expect(dates.every((d) => d.weekday == original.weekday), isTrue);
  });

  test('full days are skipped, refused ones reported, the rest booked with keys that cannot double book',
      () async {
    final shop = Shop(fullOn: {9}, refuse: {16});
    final visits = await shop.booker().book(visit(), weeks: 1, times: 3);
    expect([for (final v in visits) (v.at.day, v.booked, v.problem)], [
      (9, false, 'full'),
      (16, false, 'The shop is fully booked then'),
      (23, true, null),
    ]);
    // Full days are not even asked for.
    expect(shop.booked, hasLength(2));
    final keys = [for (final r in shop.booked) r.headers['Idempotency-Key']];
    expect(keys, ['repeat-b1-w1-1', 'repeat-b1-w1-2']);

    // Repeating the same booking again sends the same keys: booking_service returns the visits it made.
    final again = Shop(fullOn: {9}, refuse: {16});
    await again.booker().book(visit(), weeks: 1, times: 3);
    expect([for (final r in again.booked) r.headers['Idempotency-Key']], keys);
  });

  testWidgets('a completed visit can be repeated from its details', (tester) async {
    final shop = Shop();
    final client = shop.client;
    await tester.pumpWidget(MaterialApp(
      home: BookingDetailsPage(
        bookingId: 'b1',
        repository: BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online()),
        paymentApi: PaymentApi(client),
        chatApi: ChatApi(client),
        availabilityApi: AvailabilityApi(client),
        clock: () => now,
      ),
    ));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.byKey(const ValueKey('repeat-booking')));
    await tester.tap(find.byKey(const ValueKey('repeat-booking')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Every 4 weeks'));
    await tester.tap(find.text('2 visits'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('repeat-confirm')));
    await tester.pumpAndSettle();

    expect(find.text('2 visits booked'), findsOneWidget);
    expect(shop.booked, hasLength(2));
    expect(DateTime.parse((shop.booked.first.data as Map)['scheduled_at'] as String).toLocal(), DateTime(2026, 12, 30, 10, 30));
  });
}
