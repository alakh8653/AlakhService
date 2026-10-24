import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/models/booking_model.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/entities/booking.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_details_page.dart';
import 'package:alakh_service/features/booking/presentation/widgets/booking_payment.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/payment/presentation/pages/invoice_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_history_page_test.dart' show Online, booking;

/// booking_service and payment_service for one booking [b], paid by payment p1 when [paid].
FakeAdapter server(Map<String, dynamic> b, {bool paid = false, int unread = 0}) => FakeAdapter((r) {
      if (r.path.endsWith('/invoice')) return (status: 200, body: '<h1>Invoice INV-1</h1>');
      if (r.path.endsWith('/payments')) {
        return (
          status: 200,
          body: [
            if (paid) {'id': 'p1', 'booking_id': b['id'], 'status': 'COMPLETED', 'payment_method': 'upi'},
          ],
        );
      }
      if (r.path.endsWith('/messages')) {
        return (status: 200, body: {'items': <Object>[], 'total': 0, 'page': 1, 'per_page': 1, 'unread': unread, 'can_send': true, 'calling_enabled': false});
      }
      return (status: 200, body: b);
    });

Widget details(FakeAdapter adapter, String id) {
  final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
  return MaterialApp(
    home: BookingDetailsPage(
      bookingId: id,
      repository: BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online()),
      paymentApi: PaymentApi(client),
      chatApi: ChatApi(client),
      invoiceViewer: (_, html) => Text(html),
    ),
  );
}

void main() {
  final future = DateTime.now().add(const Duration(days: 3)).toUtc().toIso8601String();

  testWidgets('shows the booking\'s payment_status and links to the invoice', (tester) async {
    final adapter = server({...booking('b1', 'COMPLETED', future), 'payment_status': 'PAID'}, paid: true, unread: 2);
    await tester.pumpWidget(details(adapter, 'b1'));
    await tester.pumpAndSettle();

    expect(find.text('Paid'), findsOneWidget);
    expect(find.text('Chat, 2 unread'), findsOneWidget);
    await tester.tap(find.text('View invoice'));
    await tester.pumpAndSettle();
    expect(find.byType(InvoicePage), findsOneWidget);
    expect(find.textContaining('<h1>Invoice INV-1</h1>'), findsOneWidget);
    expect(adapter.requests.where((r) => r.path.endsWith('/payments/p1/invoice')), hasLength(1));
  });

  testWidgets('an unpaid booking has no invoice, and cancelling explains the refund policy', (tester) async {
    final adapter = server({...booking('b2', 'CONFIRMED', future), 'payment_status': 'UNPAID'});
    await tester.pumpWidget(details(adapter, 'b2'));
    await tester.pumpAndSettle();

    expect(find.text('Paid'), findsNothing);
    expect(find.text('View invoice'), findsNothing);
    await tester.tap(find.text('Cancel booking'));
    await tester.pumpAndSettle();
    expect(find.text('Cancel this booking?'), findsOneWidget);
    expect(
      find.text('Free cancellation until 2 hours before your booking. After that, a cancellation fee may apply.'),
      findsWidgets,
    );
  });

  test('payment status: the server\'s field first, else the payments list', () {
    Booking b(String? status) => BookingModel.fromJson({
          ...booking('b', 'COMPLETED', '2026-10-20T10:00:00Z'),
          if (status != null) 'payment_status': status,
        });
    expect(paymentShown(b('PAID'), null), PaymentShown.paid);
    expect(paymentShown(b('REFUNDED'), 'paid'), PaymentShown.refunded);
    expect(paymentShown(b('PARTIALLY_REFUNDED'), null), PaymentShown.partlyRefunded);
    expect(paymentShown(b('UNPAID'), 'cash'), PaymentShown.cash);
    expect(paymentShown(b('UNPAID'), null), isNull);
    // Older servers send no payment_status: the payments list decides, as before.
    expect(paymentShown(b(null), 'paid'), PaymentShown.paid);
    expect(paymentShown(b(null), 'cash'), PaymentShown.cash);
    expect(paymentShown(b(null), null), isNull);

    expect(canStillPay(b('PAID'), null), isFalse);
    expect(canStillPay(b('UNPAID'), null), isTrue);
    expect(canStillPay(b(null), 'paid'), isFalse);
  });

  test('cancelling may cost a fee within two hours of the booking', () {
    final at = DateTime(2026, 10, 23, 15);
    final b = BookingModel.fromJson(booking('b', 'CONFIRMED', at.toUtc().toIso8601String()));
    expect(b.inCancellationFeeWindow(DateTime(2026, 10, 23, 12, 59)), isFalse);
    expect(b.inCancellationFeeWindow(DateTime(2026, 10, 23, 13, 1)), isTrue);
  });
}
