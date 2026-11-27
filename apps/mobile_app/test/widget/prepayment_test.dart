import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/models/booking_model.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_details_page.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/payment/presentation/pages/payment_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_history_page_test.dart' show Online, booking;

void main() {
  final future = DateTime.now().add(const Duration(days: 2)).toUtc().toIso8601String();
  final due = DateTime.now().add(const Duration(minutes: 25)).toUtc().toIso8601String();

  test('a booking held for payment can be paid while pending', () {
    final held = BookingModel.fromJson({...booking('b1', 'PENDING', future), 'payment_due_at': due});
    expect((held.awaitingPayment, held.canPay), (true, true));
    final plain = BookingModel.fromJson(booking('b2', 'PENDING', future));
    expect((plain.awaitingPayment, plain.canPay), (false, false));
  });

  testWidgets('the booking says to pay by when, and payment there is online only', (tester) async {
    final adapter = FakeAdapter((r) {
      if (r.path.endsWith('/payments')) return (status: 200, body: <Object>[]);
      if (r.path.endsWith('/messages')) {
        return (status: 200, body: {'items': <Object>[], 'total': 0, 'page': 1, 'per_page': 1, 'unread': 0, 'can_send': true});
      }
      return (status: 200, body: {...booking('b1', 'PENDING', future), 'payment_due_at': due});
    });
    final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
    await tester.pumpWidget(MaterialApp(
      home: BookingDetailsPage(
        bookingId: 'b1',
        repository: BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online()),
        paymentApi: PaymentApi(client),
        chatApi: ChatApi(client),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Pay to keep this booking'), findsOneWidget);

    await tester.ensureVisible(find.text('Pay now'));
    await tester.tap(find.text('Pay now'));
    await tester.pumpAndSettle();
    expect(find.byType(PaymentPage), findsOneWidget);
    expect(find.text('UPI'), findsWidgets);
    expect(find.textContaining('Cash'), findsNothing);
  });
}
