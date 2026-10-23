import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../core/settings/app_settings.dart';
import '../core/theme/app_theme.dart';
import '../l10n/l10n.dart';

/// The MaterialApp, set up from the customer's display settings (a [SettingsCubit] above it).
class AppView extends StatelessWidget {
  final Widget home;

  const AppView({super.key, required this.home});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<SettingsCubit, AppSettings>(
      builder: (context, settings) => MaterialApp(
        title: 'AlakhService',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        // The phone's theme by default; the customer can pick Light or Dark in Profile.
        themeMode: settings.themeMode,
        // English or Hindi: the one picked in Profile, else the phone's language if it is one of them.
        locale: settings.locale,
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        builder: (context, child) {
          updateCurrentL10n(context.l10n);
          return child ?? const SizedBox.shrink();
        },
        home: home,
      ),
    );
  }
}
