import 'package:flutter/material.dart';

import '../../app/app_keys.dart';
import '../../l10n/l10n.dart';

/// Why the app is about to ask for location.
enum LocationPurpose {
  /// A customer: how far the provider is from them.
  eta,

  /// A provider on a job: showing their customer where they are.
  sharing,
}

/// Explains why location is needed before the system asks; true to go on and ask. With no screen
/// to show it on, goes straight to the system prompt.
Future<bool> explainLocation(LocationPurpose purpose, {BuildContext? context}) async {
  final ctx = context ?? appNavigatorKey.currentContext;
  if (ctx == null || !ctx.mounted) return true;
  final l10n = ctx.l10n;
  final go = await showDialog<bool>(
    context: ctx,
    builder: (dialogContext) => AlertDialog(
      icon: const Icon(Icons.location_on_outlined, size: 40),
      title: Text(l10n.locationWhyTitle),
      content: Text(purpose == LocationPurpose.sharing ? l10n.locationWhySharing : l10n.locationWhyEta),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(l10n.notNow)),
        FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: Text(l10n.continueLabel)),
      ],
    ),
  );
  return go ?? false;
}
