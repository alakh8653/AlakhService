import 'package:alakh_service/app/app_view.dart';
import 'package:alakh_service/core/constants/app_constants.dart';
import 'package:alakh_service/core/settings/app_settings.dart';
import 'package:alakh_service/core/theme/app_theme.dart';
import 'package:alakh_service/features/profile/presentation/pages/display_settings.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<SettingsCubit> settingsWith(Map<String, Object> saved) async {
  SharedPreferences.setMockInitialValues(saved);
  return SettingsCubit(await SharedPreferences.getInstance());
}

/// The app's MaterialApp around Profile's display settings.
Widget appWith(SettingsCubit settings) => BlocProvider.value(
      value: settings,
      child: const AppView(home: Scaffold(body: DisplaySettings())),
    );

void main() {
  test('follows the phone until a theme is chosen, and keeps the choice', () async {
    final settings = await settingsWith({});
    expect(settings.state.themeMode, ThemeMode.system);

    await settings.setThemeMode(ThemeMode.dark);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString(AppConstants.keyThemeMode), 'dark');

    // A restart reads it back.
    expect(SettingsCubit(prefs).state.themeMode, ThemeMode.dark);
  });

  test('an unknown saved value falls back to System', () async {
    final settings = await settingsWith({AppConstants.keyThemeMode: 'sepia'});
    expect(settings.state.themeMode, ThemeMode.system);
  });

  testWidgets('choosing Dark in Profile switches the app to the dark theme', (tester) async {
    final settings = await settingsWith({AppConstants.keyThemeMode: 'light'});
    await tester.pumpWidget(appWith(settings));

    expect(tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode, ThemeMode.light);
    expect(find.text('Light'), findsOneWidget);
    BuildContext ctx() => tester.element(find.byType(DisplaySettings));
    expect(Theme.of(ctx()).brightness, Brightness.light);

    await tester.tap(find.text('Theme'));
    await tester.pumpAndSettle();
    expect(find.text('System'), findsNWidgets(2)); // the sheet's option and the Language tile's value
    await tester.tap(find.text('Dark'));
    await tester.pumpAndSettle();

    expect(tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode, ThemeMode.dark);
    expect(Theme.of(ctx()).brightness, Brightness.dark);
    expect(Theme.of(ctx()).scaffoldBackgroundColor, AppTheme.darkTheme.scaffoldBackgroundColor);
    expect(find.text('Dark'), findsOneWidget); // the tile's value
    expect((await SharedPreferences.getInstance()).getString(AppConstants.keyThemeMode), 'dark');
  });

  testWidgets('System follows the phone', (tester) async {
    tester.platformDispatcher.platformBrightnessTestValue = Brightness.dark;
    addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);
    await tester.pumpWidget(appWith(await settingsWith({})));
    expect(Theme.of(tester.element(find.byType(DisplaySettings))).brightness, Brightness.dark);
  });

  test('dark theme text and muted colours read on dark surfaces', () {
    final dark = AppTheme.darkTheme;
    final palette = dark.extension<AppPalette>()!;
    for (final c in [dark.colorScheme.onSurface, palette.muted, dark.colorScheme.primary, palette.success, dark.colorScheme.error]) {
      final ratio = (c.computeLuminance() + 0.05) / (dark.colorScheme.surface.computeLuminance() + 0.05);
      expect(ratio, greaterThanOrEqualTo(4.5), reason: '$c');
    }
    // The light theme keeps its colours.
    expect(AppTheme.lightTheme.extension<AppPalette>()!.muted, AppPalette.light.muted);
  });
}
