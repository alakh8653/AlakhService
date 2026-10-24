import 'package:alakh_service/features/auth/presentation/pages/login_page.dart';
import 'package:alakh_service/features/booking/domain/entities/booking.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_history_page.dart';
import 'package:alakh_service/features/shops/data/shop_hours_api.dart';
import 'package:alakh_service/l10n/l10n.dart';
import 'package:alakh_service/shared/utils/format.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

import '../unit/shop_hours_test.dart' show hours, ist;
import 'auth_flow_test.dart' show FakeAuth, blocFor;

void main() {
  final hi = lookupAppLocalizations(const Locale('hi'));
  setUpAll(() => initializeDateFormatting('hi'));
  tearDown(() => updateCurrentL10n(englishL10n));

  testWidgets('the sign-in screen reads in Hindi, validation messages included', (tester) async {
    await tester.pumpWidget(BlocProvider.value(
      value: blocFor(FakeAuth()),
      child: MaterialApp(
        locale: const Locale('hi'),
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        builder: (context, child) {
          updateCurrentL10n(context.l10n);
          return child!;
        },
        home: const LoginPage(),
      ),
    ));
    await tester.pumpAndSettle();
    for (final text in ['फिर से स्वागत है', 'फ़ोन या ईमेल', 'पासवर्ड', 'लॉग इन करें', 'खाता नहीं है?']) {
      expect(find.text(text), findsOneWidget, reason: text);
    }
    await tester.tap(find.text('लॉग इन करें'));
    await tester.pump();
    expect(find.text('अपना फ़ोन नंबर या ईमेल डालें'), findsOneWidget);
  });

  test('opening hours, days and booking statuses in Hindi', () {
    final monday = DateTime(2026, 10, 19);
    expect(openingSummary(hours, ist(monday, '10:00'), l10n: hi)?.text, 'अभी खुला है · 2 PM पर बंद होगा');
    expect(openingSummary(hours, ist(monday, '20:00'), l10n: hi)?.text, 'बंद है · कल 10 AM पर खुलेगा');
    expect(openingSummary(hours, ist(DateTime(2026, 10, 24), '18:30'), l10n: hi)?.text, 'बंद है · सोम को 10 AM पर खुलेगा');

    final now = DateTime(2026, 10, 18, 9);
    expect(friendlyDateTime(DateTime(2026, 10, 18, 15, 30), now: now, l10n: hi), 'आज, 3:30 PM');
    expect(friendlyDay(DateTime(2026, 10, 19), now: now, l10n: hi), 'कल');
    expect(friendlyDay(DateTime(2026, 10, 20), now: now, l10n: hi), 'मंगल, 20 अक्तू॰');

    expect(bookingStatusLabel(hi, BookingStatus.pending), 'पुष्टि का इंतज़ार');
    expect(bookingStatusLabel(hi, BookingStatus.completed), 'पूरी हो गई');
    // Money keeps ₹ and Indian grouping in Hindi too.
    expect(hi.payAmount(rupees(120000)), '₹1,20,000 का भुगतान करें');
  });
}
