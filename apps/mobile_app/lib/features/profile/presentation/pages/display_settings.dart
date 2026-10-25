import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/settings/app_settings.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';

/// Profile's display settings: the theme (System, Light, Dark) and the language (System, English,
/// Hindi). Each opens a sheet to pick from and is saved straight away.
class DisplaySettings extends StatelessWidget {
  const DisplaySettings({super.key});

  static String themeLabel(AppLocalizations l10n, ThemeMode mode) => switch (mode) {
        ThemeMode.light => l10n.themeLight,
        ThemeMode.dark => l10n.themeDark,
        ThemeMode.system => l10n.themeSystem,
      };

  /// Each language by its own name, so it can be found whatever language the app is in.
  static String languageLabel(AppLocalizations l10n, Locale? locale) => switch (locale?.languageCode) {
        'en' => 'English',
        'hi' => 'हिन्दी',
        _ => l10n.languageSystem,
      };

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return BlocBuilder<SettingsCubit, AppSettings>(
      builder: (context, settings) => Column(
        children: [
          _SettingTile(
            icon: Icons.dark_mode_outlined,
            label: l10n.settingTheme,
            value: themeLabel(l10n, settings.themeMode),
            onTap: () async {
              final mode = await showChoiceSheet<ThemeMode>(
                context,
                title: l10n.settingTheme,
                selected: settings.themeMode,
                options: [for (final m in [ThemeMode.system, ThemeMode.light, ThemeMode.dark]) (m, themeLabel(l10n, m))],
              );
              if (mode != null && context.mounted) await context.read<SettingsCubit>().setThemeMode(mode);
            },
          ),
          _SettingTile(
            icon: Icons.translate,
            label: l10n.settingLanguage,
            value: languageLabel(l10n, settings.locale),
            onTap: () async {
              // A record, so "System" (no locale) can be told apart from dismissing the sheet.
              final picked = await showChoiceSheet<(Locale?,)>(
                context,
                title: l10n.settingLanguage,
                selected: (settings.locale,),
                options: [
                  for (final l in const [null, Locale('en'), Locale('hi')]) ((l,), languageLabel(l10n, l)),
                ],
              );
              if (picked != null && context.mounted) await context.read<SettingsCubit>().setLocale(picked.$1);
            },
          ),
        ],
      ),
    );
  }
}

class _SettingTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final VoidCallback onTap;

  const _SettingTile({required this.icon, required this.label, required this.value, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: context.palette.muted),
      title: Text(label, style: AppTextStyles.body1),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(value, style: AppTextStyles.body2.themed(context)),
          Icon(Icons.chevron_right, color: context.palette.muted),
        ],
      ),
      onTap: onTap,
      contentPadding: EdgeInsets.zero,
    );
  }
}

/// A bottom sheet listing [options] (value and label) with a tick on [selected]; pops with the
/// tapped value, or null if dismissed.
Future<T?> showChoiceSheet<T>(
  BuildContext context, {
  required String title,
  required List<(T, String)> options,
  required T selected,
}) {
  return showModalBottomSheet<T>(
    context: context,
    showDragHandle: true,
    builder: (sheetContext) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 8),
            child: Semantics(header: true, child: Text(title, style: AppTextStyles.heading3)),
          ),
          for (final (value, label) in options)
            ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 24),
              title: Text(label, style: AppTextStyles.body1),
              selected: value == selected,
              trailing: value == selected ? Icon(Icons.check, color: sheetContext.colors.primary) : null,
              onTap: () => Navigator.pop(sheetContext, value),
            ),
          const SizedBox(height: 8),
        ],
      ),
    ),
  );
}
