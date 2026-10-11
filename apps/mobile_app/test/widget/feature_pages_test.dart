import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/notifications/data/notifications_api.dart';
import 'package:alakh_service/features/notifications/presentation/pages/notifications_page.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/payment/presentation/pages/payment_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

ApiClient clientFor(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

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
