import 'package:alakh_service/core/constants/api_constants.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/models/booking_model.dart';
import 'package:alakh_service/features/booking/domain/entities/booking.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/queue/data/queue_api.dart';
import 'package:alakh_service/features/services/data/models/service_model.dart';
import 'package:alakh_service/features/tracking/data/tracking_api.dart';
import 'package:alakh_service/shared/utils/phone.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Map<String, dynamic> bookingJson({String status = 'CONFIRMED', String? providerId, String? notes}) => {
      'id': 'b1',
      'booking_number': 'BK-1',
      'customer_id': 'u1',
      'service_id': 's1',
      'provider_id': providerId,
      'shop_id': 'shop1',
      'status': status,
      'scheduled_at': '2026-10-12T05:30:00Z',
      'duration_minutes': 60,
      'total_amount': 49900,
      'notes': notes,
      'created_at': '2026-10-11T05:30:00Z',
    };

void main() {
  group('BookingModel', () {
    test('reads paise as rupees and splits the address from the notes', () {
      final b = BookingModel.fromJson(
        bookingJson(notes: BookingModel.composeNotes(' 12 MG Road ', 'Ring the bell')),
        serviceName: 'Haircut',
      );

      expect(b.totalAmount, 499.0);
      expect(b.address, '12 MG Road');
      expect(b.notes, 'Ring the bell');
      expect(b.serviceName, 'Haircut');
      expect(b.scheduledAt.toUtc(), DateTime.utc(2026, 10, 12, 5, 30));
    });

    test('actions follow the booking status', () {
      final confirmed = BookingModel.fromJson(bookingJson());
      expect(confirmed.canCancel, isTrue);
      expect(confirmed.canPay, isTrue);
      expect(confirmed.canTrack, isFalse);

      final enRoute = BookingModel.fromJson(bookingJson(status: BookingStatus.enRoute, providerId: 'p1'));
      expect(enRoute.canCancel, isFalse);
      expect(enRoute.canTrack, isTrue);

      final done = BookingModel.fromJson(bookingJson(status: BookingStatus.completed, providerId: 'p1'));
      expect(done.canRate, isTrue);
      expect(done.canTrack, isFalse);

      expect(BookingModel.fromJson(bookingJson(status: BookingStatus.pending)).canPay, isFalse);
    });
  });

  test('ServiceModel reads catalogue prices in paise', () {
    final s = ServiceModel.fromJson(const {
      'id': 's1',
      'shop_id': 'shop1',
      'name': 'Haircut',
      'description': 'Classic cut',
      'category': 'salon',
      'price_cents': 25000,
      'duration_minutes': 30,
      'is_active': true,
    });

    expect(s.basePrice, 250.0);
    expect(s.priceUnit, '30 min');
    expect(s.shopId, 'shop1');
  });

  test('phone numbers are normalised to E.164', () {
    expect(normalizePhone('98765 43210'), '+919876543210');
    expect(normalizePhone('+91 98765-43210'), '+919876543210');
    expect(normalizeIdentifier('Me@Example.com '), 'me@example.com');
  });

  group('feature APIs', () {
    test('payment sends only the booking, method and idempotency key', () async {
      final adapter = FakeAdapter((_) => (status: 201, body: {'id': 'pay1', 'amount_cents': 49900, 'status': 'PENDING'}));
      final api = PaymentApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));

      final key = PaymentApi.newIdempotencyKey();
      final result = await api.payForBooking(bookingId: 'b1', method: 'upi', idempotencyKey: key);

      expect(adapter.requests.single.path, ApiConstants.initiatePayment);
      expect(adapter.requests.single.data, {'booking_id': 'b1', 'payment_method': 'upi', 'idempotency_key': key});
      expect(key.length, greaterThanOrEqualTo(8));
      expect(result.amount, 499.0);
      expect(result.status, 'PENDING');
    });

    test('tracking returns null until the provider shares a location', () async {
      final adapter = FakeAdapter((_) => (status: 404, body: {'detail': 'No location'}));
      final api = TrackingApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));

      expect(await api.providerLocation('p1'), isNull);
    });

    test('queue finds an open queue and reports position', () async {
      final adapter = FakeAdapter((r) => r.path == ApiConstants.queues
          ? (status: 200, body: [
              {'id': 'q1'},
            ])
          : (status: 200, body: {'queue_id': 'q1', 'id': 'e1', 'position': 2, 'estimated_wait_minutes': 10}));
      final api = QueueApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));

      expect(await api.openQueueFor('s1'), 'q1');
      expect(adapter.requests.first.queryParameters, {'service_id': 's1'});
      final ticket = await api.position(queueId: 'q1', customerId: 'u1');
      expect(ticket!.position, 2);
      expect(ticket.estimatedWaitMinutes, 10);
    });
  });
}
