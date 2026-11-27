import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../security/app_lock.dart';

/// Profile's "App lock" switch: asks for the phone's fingerprint, face or PIN when the app opens. Shown
/// only on phones that can check (a screen lock or biometrics is set up).
class AppLockSetting extends StatefulWidget {
  /// From the app's service locator when left out.
  final AppLockCubit? lock;

  const AppLockSetting({super.key, this.lock});

  @override
  State<AppLockSetting> createState() => _AppLockSettingState();
}

class _AppLockSettingState extends State<AppLockSetting> {
  late final AppLockCubit? _lock = widget.lock ?? (sl.isRegistered<AppLockCubit>() ? sl<AppLockCubit>() : null);
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _lock?.checkAvailable();
  }

  Future<void> _toggle(bool on) async {
    final lock = _lock!;
    final l10n = context.l10n;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    if (on) {
      final enabled = await lock.enable(l10n.appLockReason);
      if (!enabled) {
        messenger.showSnackBar(SnackBar(content: Text(l10n.appLockNotConfirmed), backgroundColor: AppColors.error));
      }
    } else {
      await lock.disable();
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final lock = _lock;
    if (lock == null) return const SizedBox.shrink();
    final l10n = context.l10n;
    return BlocBuilder<AppLockCubit, AppLockState>(
      bloc: lock,
      builder: (context, state) {
        if (state.available != true) return const SizedBox.shrink();
        return SwitchListTile(
          secondary: Icon(Icons.fingerprint, color: context.palette.muted),
          title: Text(l10n.appLockSetting, style: AppTextStyles.body1),
          subtitle: Text(l10n.appLockSettingHint, style: AppTextStyles.caption.themed(context)),
          value: state.enabled,
          onChanged: _busy ? null : _toggle,
          contentPadding: EdgeInsets.zero,
        );
      },
    );
  }
}
