import 'package:alakh_service/core/constants/support_constants.dart';
import 'package:alakh_service/core/errors/failures.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/dispute_api.dart';
import 'package:alakh_service/features/booking/domain/entities/booking.dart';
import 'package:alakh_service/features/booking/domain/repositories/booking_repository.dart';
import 'package:alakh_service/features/help/presentation/help_support_page.dart';
import 'package:alakh_service/l10n/l10n.dart';
import 'package:dartz/dartz.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Booking booking(String id, String number, String status) => Booking(
      id: id,
      bookingNumber: number,
      userId: 'u1',
      serviceId: 's1',
      serviceName: 'Haircut',
      shopId: 'sh1',
      status: status,
      scheduledAt: DateTime(2026, 10, 20, 11),
      address: '',
      totalAmount: 300,
      createdAt: DateTime(2026, 10, 1),
    );

class FakeBookings implements BookingRepository {
  final List<Booking> bookings;

  FakeBookings(this.bookings);

  @override
  Future<Either<Failure, List<Booking>>> getUserBookings({int page = 1}) async => Right(bookings);

  @override
  dynamic noSuchMethod(Invocation invocation) => throw UnimplementedError();
}

void main() {
  late List<Uri> opened;
  late List<String> requests;

  Widget page({Locale? locale, bool opens = true}) {
    final adapter = FakeAdapter((req) {
      requests.add('${req.method} ${req.path}');
      return (status: 200, body: <String, dynamic>{});
    });
    return MaterialApp(
      locale: locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      home: HelpSupportPage(
        open: (uri) async {
          opened.add(uri);
          return opens;
        },
        bookings: FakeBookings([
          booking('b1', 'AS-1001', BookingStatus.completed),
          booking('b2', 'AS-1002', BookingStatus.pending),
        ]),
        disputeApi: DisputeApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore())),
      ),
    );
  }

  // Tall enough for the whole page, so every question and contact is on screen.
  Future<void> pumpPage(WidgetTester tester, Widget app) async {
    tester.view.physicalSize = const Size(800, 4000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(app);
  }

  setUp(() {
    opened = [];
    requests = [];
  });

  testWidgets('FAQs expand to their answer and the search narrows them', (tester) async {
    await pumpPage(tester, page());
    expect(find.text('How do I cancel a booking?'), findsOneWidget);
    expect(find.textContaining('until the provider is on the way'), findsNothing);

    await tester.tap(find.text('How do I cancel a booking?'));
    await tester.pumpAndSettle();
    expect(find.textContaining('until the provider is on the way'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'refund');
    await tester.pumpAndSettle();
    expect(find.text('How do refunds work?'), findsOneWidget);
    expect(find.text('How do I book a service?'), findsNothing);

    await tester.enterText(find.byType(TextField), 'zzzz');
    await tester.pumpAndSettle();
    expect(find.textContaining('No answers match'), findsOneWidget);
  });

  testWidgets('every topic the customer asks about is covered', (tester) async {
    await pumpPage(tester, page());
    for (final topic in [
      'Booking',
      'Cancelling & rescheduling',
      'Payments & refunds',
      'Pickup & drop',
      'Home visits',
      'Reviews',
      'Account & privacy',
    ]) {
      expect(find.text(topic), findsOneWidget, reason: topic);
    }
    // Sessions: signing out here and of other devices.
    expect(find.text('How do I sign out, or sign out of other devices?'), findsOneWidget);
  });

  testWidgets('email and call reach the platform support team, never a shop', (tester) async {
    await pumpPage(tester, page());
    await tester.tap(find.text('Email support'));
    await tester.tap(find.text('Call support'));
    await tester.pump();

    expect(opened.map((u) => u.scheme), ['mailto', 'tel']);
    expect(opened[0].path, SupportContact.email);
    expect(opened[0].queryParameters['subject'], 'AlakhService support');
    expect(opened[1].path, SupportContact.phone);
  });

  testWidgets('when no app can open the link, it says how to reach support', (tester) async {
    await pumpPage(tester, page(opens: false));
    await tester.tap(find.text('Call support'));
    await tester.pump();
    expect(find.textContaining('Write to ${SupportContact.email}'), findsOneWidget);
  });

  testWidgets('a finished booking is reported in the app; another is emailed with its number', (tester) async {
    await pumpPage(tester, page());
    await tester.tap(find.text('Report a problem with a booking'));
    await tester.pumpAndSettle();

    // Completed: the booking's own problem report.
    await tester.tap(find.textContaining('AS-1001'));
    await tester.pumpAndSettle();
    expect(find.text('What went wrong?'), findsOneWidget);
    await tester.enterText(find.widgetWithText(TextField, 'Tell us what happened'), 'Bad cut');
    await tester.pump();
    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();
    expect(requests, contains('POST /api/v1/disputes'));
    expect(opened, isEmpty);
    tester.state<ScaffoldMessengerState>(find.byType(ScaffoldMessenger)).hideCurrentSnackBar();
    await tester.pumpAndSettle();

    // Pending: an email to support about it.
    await tester.tap(find.text('Report a problem with a booking'));
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('AS-1002'));
    await tester.pumpAndSettle();
    expect(opened.single.path, SupportContact.email);
    expect(opened.single.queryParameters['subject'], 'Problem with booking #AS-1002');
    expect(opened.single.queryParameters['body'], startsWith('Booking number: AS-1002'));
  });

  testWidgets('reads in Hindi', (tester) async {
    await pumpPage(tester, page(locale: const Locale('hi')));
    await tester.pumpAndSettle();
    expect(find.text('मदद और सहायता'), findsOneWidget);
    expect(find.text('बुकिंग कैसे रद्द करें?'), findsOneWidget);
  });
}
