import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/directions/data/shop_location_api.dart';
import 'package:alakh_service/features/directions/presentation/how_to_get_there_sheet.dart';
import 'package:alakh_service/features/notifications/data/notifications_api.dart';
import 'package:alakh_service/features/notifications/presentation/pages/notifications_page.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/payment/presentation/pages/payment_page.dart';
import 'package:alakh_service/features/queue/data/queue_api.dart';
import 'package:alakh_service/features/queue/presentation/pages/queue_status_page.dart';
import 'package:alakh_service/l10n/l10n.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

ApiClient client(FakeHandler handler) => ApiClient(dio: fakeDio(FakeAdapter(handler)), tokens: MemoryTokenStore());

Widget hindi(Widget home) => MaterialApp(
      locale: const Locale('hi'),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      home: home,
    );

void main() {
  final hi = lookupAppLocalizations(const Locale('hi'));

  testWidgets('notifications read in Hindi', (tester) async {
    await tester.pumpWidget(hindi(NotificationsPage(
      notificationsApi: NotificationsApi(client((_) => (status: 200, body: {'items': <Object>[]}))),
    )));
    await tester.pumpAndSettle();
    expect(find.text('अभी कोई सूचना नहीं'), findsOneWidget);
  });

  testWidgets('payment reads in Hindi', (tester) async {
    await tester.pumpWidget(hindi(PaymentPage(
      amount: 499,
      bookingId: 'b1',
      bookingNumber: 'BK-1',
      paymentApi: PaymentApi(client((_) => (status: 200, body: null))),
    )));
    await tester.pumpAndSettle();
    for (final text in ['भुगतान', 'भुगतान का तरीका', 'नेट बैंकिंग', 'नकद भुगतान करें', '₹499 का भुगतान करें']) {
      expect(find.text(text), findsOneWidget, reason: text);
    }
  });

  testWidgets('the walk-in queue reads in Hindi', (tester) async {
    await tester.pumpWidget(hindi(QueueStatusPage(
      serviceName: 'Haircut',
      customerId: 'u1',
      ticket: const QueueTicket(queueId: 'q1', entryId: 'e1', position: 3, estimatedWaitMinutes: 20, peopleAhead: 2),
      queueApi: QueueApi(client((_) => (status: 200, body: {'position': 3, 'estimated_wait_minutes': 20, 'people_ahead': 2}))),
    )));
    await tester.pumpAndSettle();
    expect(find.text('आपका नंबर'), findsOneWidget);
    expect(find.text('कतार छोड़ें'), findsOneWidget);
    expect(hi.queueAhead(2), 'आपसे आगे 2 लोग');
    expect(hi.queueAhead(0), 'आपसे आगे कोई नहीं');
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('"How to get there" reads in Hindi', (tester) async {
    await tester.pumpWidget(hindi(Scaffold(
      body: HowToGetThereSheet(
        shopId: 'sh1',
        api: ShopLocationApi(client((_) => (
              status: 200,
              body: {'id': 'sh1', 'name': 'Demo Salon', 'address': '12 MG Road', 'city': 'Pune', 'latitude': 18.52, 'longitude': 73.85},
            ))),
        open: (_) async => true,
      ),
    )));
    await tester.pumpAndSettle();
    for (final text in ['वहाँ कैसे पहुँचें', 'गाड़ी से जाएँ', 'सार्वजनिक परिवहन', 'पैदल', 'Ola, Rapido या कोई और राइड ऐप']) {
      expect(find.text(text), findsOneWidget, reason: text);
    }
  });
}
