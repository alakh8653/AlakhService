import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_details_page.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/payment/data/razorpay_checkout.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_history_page_test.dart' show Online, booking;
import 'feature_pages_test.dart' show FakeCheckout;

/// booking_service with one completed booking; payment_service with [tipped] rupees already tipped (or none),
/// opening a Razorpay order for a new tip and completing it once verified.
FakeAdapter server({int? tipped}) => FakeAdapter((r) {
      if (r.path.endsWith('/payments/tips')) {
        final cents = (r.data as Map)['amount_cents'] as int;
        return (status: 201, body: {
          'id': 't1',
          'amount_cents': cents,
          'status': 'PENDING',
          'checkout': {'key_id': 'rzp_test', 'order_id': 'order_t1', 'amount_cents': cents, 'currency': 'INR'},
        });
      }
      if (r.path.endsWith('/payments/t1/verify')) return (status: 200, body: {'id': 't1', 'amount_cents': 7500, 'status': 'COMPLETED'});
      if (r.path.endsWith('/payments')) {
        final tips = r.queryParameters['purpose'] == 'TIP' && tipped != null;
        return (status: 200, body: [if (tips) {'id': 't0', 'booking_id': 'b1', 'amount_cents': tipped * 100, 'status': 'COMPLETED'}]);
      }
      if (r.path.endsWith('/messages')) {
        return (status: 200, body: {'items': <Object>[], 'total': 0, 'page': 1, 'per_page': 1, 'unread': 0, 'can_send': true, 'calling_enabled': false});
      }
      return (status: 200, body: booking('b1', 'COMPLETED', '2026-10-10T05:30:00Z'));
    });

Widget details(FakeAdapter adapter, CheckoutLauncher checkout) {
  final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
  return MaterialApp(
    home: BookingDetailsPage(
      bookingId: 'b1',
      repository: BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online()),
      paymentApi: PaymentApi(client),
      chatApi: ChatApi(client),
      checkoutLauncher: checkout,
    ),
  );
}

void main() {
  testWidgets('a completed booking can be tipped online, with a suggested or own amount', (tester) async {
    final adapter = server();
    final checkout = FakeCheckout(const CheckoutPaid(orderId: 'order_t1', paymentId: 'pay_t1', signature: 'sig'));
    await tester.pumpWidget(details(adapter, checkout));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('Add a tip'));
    await tester.tap(find.text('Add a tip'));
    await tester.pumpAndSettle();
    expect(find.text('Tip your professional'), findsOneWidget);
    expect(find.text('Tip ₹50'), findsOneWidget); // the middle suggestion is picked

    await tester.enterText(find.byType(TextField), '5');
    await tester.pump();
    expect(find.text('Enter ₹10 to ₹2,000'), findsOneWidget);
    final pay = find.widgetWithText(FilledButton, 'Tip ₹5');
    expect(tester.widget<FilledButton>(pay).onPressed, isNull);

    await tester.enterText(find.byType(TextField), '75');
    await tester.pump();
    await tester.tap(find.text('Tip ₹75'));
    await tester.pumpAndSettle();

    final started = adapter.requests.singleWhere((r) => r.path.endsWith('/payments/tips'));
    expect((started.data as Map)['amount_cents'], 7500);
    expect((started.data as Map)['booking_id'], 'b1');
    expect(checkout.opened?.orderId, 'order_t1');
    expect(adapter.requests.where((r) => r.path.endsWith('/payments/t1/verify')), hasLength(1));
    expect(find.text('Tip your professional'), findsNothing); // the sheet closed
    expect(find.text('You tipped ₹75. Thank you!'), findsWidgets);
    expect(find.text('Add a tip'), findsNothing);
  });

  testWidgets('a booking already tipped says so instead of asking again', (tester) async {
    await tester.pumpWidget(details(server(tipped: 50), FakeCheckout(const CheckoutCancelled())));
    await tester.pumpAndSettle();
    expect(find.text('You tipped ₹50. Thank you!'), findsOneWidget);
    expect(find.text('Add a tip'), findsNothing);
  });

  testWidgets('closing the checkout leaves no tip and keeps the sheet open', (tester) async {
    final adapter = server();
    await tester.pumpWidget(details(adapter, FakeCheckout(const CheckoutCancelled())));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Add a tip'));
    await tester.tap(find.text('Add a tip'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Tip ₹50'));
    await tester.pumpAndSettle();
    expect(adapter.requests.where((r) => r.path.contains('/verify')), isEmpty);
    expect(find.text('Tip your professional'), findsOneWidget);
  });
}
