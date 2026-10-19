import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/settings/app_settings.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';

/// Profile's display settings: the theme (System, Light, Dark). Each opens a sheet to pick from and
/// is saved straight away.
class DisplaySettings extends StatelessWidget {
  const DisplaySettings({super.key});

  static String themeLabel(ThemeMode mode) => switch (mode) {
        ThemeMode.light => 'Light',
        ThemeMode.dark => 'Dark',
        ThemeMode.system => 'System',
      };

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<SettingsCubit, AppSettings>(
      builder: (context, settings) => Column(
        children: [
          _SettingTile(
            icon: Icons.dark_mode_outlined,
            label: 'Theme',
            value: themeLabel(settings.themeMode),
            onTap: () async {
              final mode = await showChoiceSheet<ThemeMode>(
                context,
                title: 'Theme',
                selected: settings.themeMode,
                options: [for (final m in [ThemeMode.system, ThemeMode.light, ThemeMode.dark]) (m, themeLabel(m))],
              );
              if (mode != null && context.mounted) await context.read<SettingsCubit>().setThemeMode(mode);
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
