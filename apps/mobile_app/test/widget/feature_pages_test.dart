import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/notifications/data/notifications_api.dart';
import 'package:alakh_service/features/notifications/presentation/pages/notifications_page.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/payment/data/razorpay_checkout.dart';
import 'package:alakh_service/features/payment/presentation/pages/payment_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

ApiClient clientFor(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

class FakeCheckout implements CheckoutLauncher {
  final CheckoutOutcome outcome;
  GatewayCheckout? opened;

  FakeCheckout(this.outcome);

  @override
  Future<CheckoutOutcome> open(GatewayCheckout checkout, {required String description, String? contact, String? email}) async {
    opened = checkout;
    return outcome;
  }
}

/// payment_service: initiate opens order_1; verify completes it.
FakeAdapter paymentServer() => FakeAdapter((r) => r.path.endsWith('/verify')
    ? (status: 200, body: {'id': 'pay1', 'amount_cents': 49900, 'status': 'COMPLETED', 'checkout': null})
    : (status: 201, body: {
        'id': 'pay1',
        'amount_cents': 49900,
        'status': 'PENDING',
        'checkout': {'gateway': 'razorpay', 'key_id': 'rzp_test', 'order_id': 'order_1', 'amount_cents': 49900, 'currency': 'INR'},
      }));

void main() {
  testWidgets('payment page reports the amount the server charged', (tester) async {
    final adapter = FakeAdapter((_) => (status: 201, body: {'id': 'pay1', 'amount_cents': 59900, 'status': 'PENDING'}));
    await tester.pumpWidget(MaterialApp(
      home: PaymentPage(amount: 499, bookingId: 'booking-123', paymentApi: PaymentApi(clientFor(adapter))),
    ));

    await tester.tap(find.text('Pay in cash'));
    await tester.pump();
    await tester.tap(find.text('Pay ₹499.00'));
    await tester.pumpAndSettle();

    expect(adapter.requests.single.data['payment_method'], 'cash');
    expect(find.text('Payment Recorded'), findsOneWidget);
    expect(find.textContaining('₹599.00 in cash'), findsOneWidget);
  });

  testWidgets('online payment opens checkout and completes once the server verifies it', (tester) async {
    final adapter = paymentServer();
    final checkout = FakeCheckout(const CheckoutPaid(orderId: 'order_1', paymentId: 'pay_rzp', signature: 'sig'));
    await tester.pumpWidget(MaterialApp(
      home: PaymentPage(
        amount: 499,
        bookingId: 'booking-123',
        paymentApi: PaymentApi(clientFor(adapter)),
        checkoutLauncher: checkout,
      ),
    ));

    await tester.tap(find.text('Pay ₹499.00'));
    await tester.pumpAndSettle();

    expect(checkout.opened!.orderId, 'order_1');
    expect(adapter.requests.last.path, '/api/v1/payments/pay1/verify');
    expect(adapter.requests.last.data, {
      'razorpay_order_id': 'order_1',
      'razorpay_payment_id': 'pay_rzp',
      'razorpay_signature': 'sig',
    });
    expect(find.text('Payment Successful'), findsOneWidget);
    expect(find.text('₹499.00 paid.'), findsOneWidget);
  });

  testWidgets('cancelling checkout charges nothing and verifies nothing', (tester) async {
    final adapter = paymentServer();
    await tester.pumpWidget(MaterialApp(
      home: PaymentPage(
        amount: 499,
        bookingId: 'booking-123',
        paymentApi: PaymentApi(clientFor(adapter)),
        checkoutLauncher: FakeCheckout(const CheckoutCancelled()),
      ),
    ));

    await tester.tap(find.text('Pay ₹499.00'));
    await tester.pumpAndSettle();

    expect(adapter.requests.map((r) => r.path), ['/api/v1/payments/initiate']);
    expect(find.text('Payment cancelled. You have not been charged.'), findsOneWidget);
    expect(find.text('Payment Successful'), findsNothing);
  });

  testWidgets('payment page shows the API error', (tester) async {
    final adapter = FakeAdapter((_) => (status: 409, body: {'detail': 'This booking cannot be paid yet'}));
    await tester.pumpWidget(MaterialApp(
      home: PaymentPage(amount: 499, bookingId: 'booking-123', paymentApi: PaymentApi(clientFor(adapter))),
    ));

    await tester.tap(find.text('Pay ₹499.00'));
    await tester.pumpAndSettle();

    expect(find.text('This booking cannot be paid yet'), findsOneWidget);
  });

  testWidgets('notifications load and can all be marked read', (tester) async {
    var read = false;
    final adapter = FakeAdapter((r) {
      if (r.method == 'POST') {
        read = true;
        return (status: 200, body: {'updated': 1});
      }
      return (status: 200, body: {
        'items': [
          {
            'id': 'n1',
            'title': 'Booking confirmed',
            'body': 'See you tomorrow',
            'is_read': read,
            'created_at': DateTime.now().toUtc().toIso8601String(),
          },
        ],
      });
    });
    await tester.pumpWidget(MaterialApp(home: NotificationsPage(notificationsApi: NotificationsApi(clientFor(adapter)))));
    await tester.pumpAndSettle();

    expect(find.text('Booking confirmed'), findsOneWidget);
    await tester.tap(find.text('Mark all read'));
    await tester.pumpAndSettle();

    expect(read, isTrue);
    expect(find.text('Mark all read'), findsNothing);
  });
}
