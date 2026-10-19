import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../constants/app_constants.dart';

/// The customer's display choices: light, dark or the phone's theme, and the app's language
/// ([locale] null follows the phone).
class AppSettings extends Equatable {
  final ThemeMode themeMode;
  final Locale? locale;

  const AppSettings({this.themeMode = ThemeMode.system, this.locale});

  @override
  List<Object?> get props => [themeMode, locale];
}

/// Holds [AppSettings] and keeps them in shared_preferences, so they survive a restart.
class SettingsCubit extends Cubit<AppSettings> {
  final SharedPreferences _prefs;

  /// The languages the app is translated into, as stored.
  static const supportedLanguages = {'en', 'hi'};

  SettingsCubit(this._prefs) : super(_read(_prefs));

  static AppSettings _read(SharedPreferences prefs) {
    final theme = prefs.getString(AppConstants.keyThemeMode);
    final language = prefs.getString(AppConstants.keyLanguage);
    return AppSettings(
      themeMode: ThemeMode.values.where((m) => m.name == theme).firstOrNull ?? ThemeMode.system,
      locale: supportedLanguages.contains(language) ? Locale(language!) : null,
    );
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    emit(AppSettings(themeMode: mode, locale: state.locale));
    await _prefs.setString(AppConstants.keyThemeMode, mode.name);
  }

  /// [locale] null goes back to the phone's language.
  Future<void> setLocale(Locale? locale) async {
    emit(AppSettings(themeMode: state.themeMode, locale: locale));
    if (locale == null) {
      await _prefs.remove(AppConstants.keyLanguage);
    } else {
      await _prefs.setString(AppConstants.keyLanguage, locale.languageCode);
    }
  }
}
