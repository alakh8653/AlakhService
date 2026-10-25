import 'package:flutter/widgets.dart';

import 'app_localizations.dart';
import 'app_localizations_en.dart';

export 'app_localizations.dart';

/// English, for widgets built without the app's localization delegates (most widget tests) and
/// before the first frame.
final AppLocalizations englishL10n = AppLocalizationsEn();

AppLocalizations _current = englishL10n;

/// The strings of the language on screen, for code with no BuildContext: validators and the
/// messages repositories build for failures. Kept in step by [AppView].
AppLocalizations get currentL10n => _current;

/// Called by the app's MaterialApp builder whenever the language shown changes.
void updateCurrentL10n(AppLocalizations l10n) => _current = l10n;

extension L10nContext on BuildContext {
  /// The app's strings in the language shown: `context.l10n.bookNow`.
  AppLocalizations get l10n => AppLocalizations.of(this) ?? englishL10n;
}
