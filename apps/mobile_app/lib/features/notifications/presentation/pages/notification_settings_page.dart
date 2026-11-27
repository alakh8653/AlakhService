import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../data/notifications_api.dart';

/// How the customer wants to be told: push, SMS and email each on or off, and quiet hours for updates
/// that can wait. Every notice stays in the app's own list whatever is switched off.
class NotificationSettingsPage extends StatefulWidget {
  final NotificationsApi? api;

  const NotificationSettingsPage({super.key, this.api});

  @override
  State<NotificationSettingsPage> createState() => _NotificationSettingsPageState();
}

class _NotificationSettingsPageState extends State<NotificationSettingsPage> {
  late final NotificationsApi _api = widget.api ?? sl<NotificationsApi>();
  NotificationPreferences? _prefs;
  String? _error;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final prefs = await _api.preferences();
      if (mounted) setState(() => _prefs = prefs);
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  Future<void> _save(NotificationPreferences next) async {
    final before = _prefs;
    final messenger = ScaffoldMessenger.of(context);
    setState(() {
      _prefs = next; // at once; put back if it fails
      _saving = true;
    });
    try {
      final saved = await _api.savePreferences(next);
      if (mounted) setState(() => _prefs = saved);
    } catch (e) {
      if (mounted) setState(() => _prefs = before);
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String _hour(int h) => MaterialLocalizations.of(context).formatTimeOfDay(TimeOfDay(hour: h, minute: 0));

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final prefs = _prefs;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.notificationSettingsTitle)),
      body: prefs == null
          ? (_error != null ? AppErrorWidget(message: _error!, onRetry: _load) : LoadingIndicator(message: l10n.loadingMore))
          : ListView(
              padding: const EdgeInsets.symmetric(vertical: 8),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                  child: Text(l10n.notificationSettingsHint, style: AppTextStyles.body2.themed(context)),
                ),
                SwitchListTile(
                  key: const ValueKey('pref-push'),
                  secondary: const Icon(Icons.notifications_active_outlined),
                  title: Text(l10n.notifyPush),
                  subtitle: Text(l10n.notifyPushHint),
                  value: prefs.push,
                  onChanged: _saving ? null : (v) => _save(prefs.copyWith(push: v)),
                ),
                SwitchListTile(
                  key: const ValueKey('pref-sms'),
                  secondary: const Icon(Icons.sms_outlined),
                  title: Text(l10n.notifySms),
                  subtitle: Text(l10n.notifySmsHint),
                  value: prefs.sms,
                  onChanged: _saving ? null : (v) => _save(prefs.copyWith(sms: v)),
                ),
                SwitchListTile(
                  key: const ValueKey('pref-email'),
                  secondary: const Icon(Icons.email_outlined),
                  title: Text(l10n.notifyEmail),
                  value: prefs.email,
                  onChanged: _saving ? null : (v) => _save(prefs.copyWith(email: v)),
                ),
                const Divider(),
                SwitchListTile(
                  key: const ValueKey('pref-quiet'),
                  secondary: const Icon(Icons.bedtime_outlined),
                  title: Text(l10n.quietHours),
                  subtitle: Text(l10n.quietHoursHint),
                  value: prefs.quietStart != null,
                  onChanged: _saving
                      ? null
                      : (on) => _save(on ? prefs.withQuiet(22, 7) : prefs.withoutQuiet()),
                ),
                if (prefs.quietStart != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(72, 0, 16, 8),
                    child: Row(
                      children: [
                        Text(l10n.quietFrom, style: AppTextStyles.body2.themed(context)),
                        const SizedBox(width: 8),
                        DropdownButton<int>(
                          key: const ValueKey('quiet-start'),
                          value: prefs.quietStart,
                          items: [for (var h = 0; h < 24; h++) DropdownMenuItem(value: h, child: Text(_hour(h)))],
                          onChanged: _saving ? null : (h) => _save(prefs.withQuiet(h!, prefs.quietEnd!)),
                        ),
                        const SizedBox(width: 16),
                        Text(l10n.quietTo, style: AppTextStyles.body2.themed(context)),
                        const SizedBox(width: 8),
                        DropdownButton<int>(
                          key: const ValueKey('quiet-end'),
                          value: prefs.quietEnd,
                          items: [for (var h = 0; h < 24; h++) DropdownMenuItem(value: h, child: Text(_hour(h)))],
                          onChanged: _saving ? null : (h) => _save(prefs.withQuiet(prefs.quietStart!, h!)),
                        ),
                      ],
                    ),
                  ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                  child: Text(
                    l10n.notifyAlwaysInApp,
                    style: AppTextStyles.caption.copyWith(color: context.palette.muted),
                  ),
                ),
              ],
            ),
    );
  }
}
