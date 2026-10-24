import 'package:alakh_service/app/app_view.dart';
import 'package:alakh_service/core/constants/app_constants.dart';
import 'package:alakh_service/core/settings/app_settings.dart';
import 'package:alakh_service/features/profile/presentation/pages/display_settings.dart';
import 'package:alakh_service/l10n/l10n.dart';
import 'package:alakh_service/shared/utils/validators.dart';
import 'package:alakh_service/shared/widgets/bottom_nav_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<SettingsCubit> settingsWith(Map<String, Object> saved) async {
  SharedPreferences.setMockInitialValues(saved);
  return SettingsCubit(await SharedPreferences.getInstance());
}

Widget appWith(SettingsCubit settings) => BlocProvider.value(
      value: settings,
      child: AppView(
        home: Scaffold(
          body: const DisplaySettings(),
          bottomNavigationBar: AppBottomNavBar(currentIndex: 0, onTap: (_) {}),
        ),
      ),
    );

void main() {
  tearDown(() => updateCurrentL10n(englishL10n));

  testWidgets('picking हिन्दी in Profile switches the app to Hindi and keeps it', (tester) async {
    final settings = await settingsWith({});
    await tester.pumpWidget(appWith(settings));
    expect(find.text('Language'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);

    await tester.tap(find.text('Language'));
    await tester.pumpAndSettle();
    expect(find.text('English'), findsOneWidget);
    await tester.tap(find.text('हिन्दी'));
    await tester.pumpAndSettle();

    expect(tester.widget<MaterialApp>(find.byType(MaterialApp)).locale, const Locale('hi'));
    // The settings and the tab bar now read in Hindi.
    for (final hindi in ['भाषा', 'थीम', 'होम', 'सेवाएँ', 'बुकिंग', 'प्रोफ़ाइल']) {
      expect(find.text(hindi), findsOneWidget, reason: hindi);
    }
    expect(find.text('हिन्दी'), findsOneWidget); // the tile's value
    expect((await SharedPreferences.getInstance()).getString(AppConstants.keyLanguage), 'hi');
    // Code without a BuildContext (form validators) follows too.
    expect(Validators.indianMobile(''), 'मोबाइल नंबर ज़रूरी है');

    // Back to the phone's language (English in tests).
    await tester.tap(find.text('भाषा'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('फ़ोन के अनुसार').last);
    await tester.pumpAndSettle();
    expect(tester.widget<MaterialApp>(find.byType(MaterialApp)).locale, isNull);
    expect(find.text('Home'), findsOneWidget);
    expect((await SharedPreferences.getInstance()).getString(AppConstants.keyLanguage), isNull);
  });

  testWidgets('a saved language is used from the start', (tester) async {
    await tester.pumpWidget(appWith(await settingsWith({AppConstants.keyLanguage: 'hi'})));
    expect(find.text('होम'), findsOneWidget);
  });

  testWidgets('with nothing saved, a phone in Hindi gets Hindi and any other language English', (tester) async {
    tester.platformDispatcher.localesTestValue = const [Locale('hi', 'IN')];
    addTearDown(tester.platformDispatcher.clearLocalesTestValue);
    await tester.pumpWidget(appWith(await settingsWith({})));
    expect(find.text('होम'), findsOneWidget);

    tester.platformDispatcher.localesTestValue = const [Locale('ta', 'IN')];
    await tester.pumpAndSettle();
    expect(find.text('Home'), findsOneWidget);
  });

  test('plurals and placeholders read naturally in both languages', () {
    final hi = lookupAppLocalizations(const Locale('hi'));
    expect(englishL10n.reviewsCount(1), '1 review');
    expect(englishL10n.reviewsCount(12), '12 reviews');
    expect(hi.reviewsCount(1), '1 समीक्षा');
    expect(hi.reviewsCount(12), '12 समीक्षाएँ');
    expect(hi.payAmount('₹1,499'), '₹1,499 का भुगतान करें');
  });
}
