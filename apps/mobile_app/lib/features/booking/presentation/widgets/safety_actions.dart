import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:location/location.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../jobs/data/location_reporter.dart';
import '../../data/trust_api.dart';

/// Hands text to the system share sheet (replaceable in tests).
typedef ShareText = Future<void> Function(String text);

/// Opens a link outside the app, such as tel:112 (replaceable in tests).
typedef OpenUri = Future<bool> Function(Uri uri);

/// Where the device is right now, if location is already allowed; null otherwise (replaceable in tests).
typedef CurrentFix = Future<Fix?> Function();

Future<void> systemShare(String text) async {
  try {
    await SharePlus.instance.share(ShareParams(text: text));
  } on MissingPluginException {
    // No share sheet (desktop, tests): the link goes to the clipboard instead.
    await Clipboard.setData(ClipboardData(text: text));
  }
}

Future<bool> openExternalUri(Uri uri) => launchUrl(uri, mode: LaunchMode.externalApplication);

/// In an emergency nobody is asked for permission first: the position goes along only when location
/// is already on and allowed, and only if it comes quickly.
Future<Fix?> permittedFix() async {
  try {
    final location = Location();
    if (!await location.serviceEnabled()) return null;
    final permission = await location.hasPermission();
    if (permission != PermissionStatus.granted && permission != PermissionStatus.grantedLimited) return null;
    final p = await location.getLocation().timeout(const Duration(seconds: 5));
    return Fix(p.latitude, p.longitude, accuracy: p.accuracy);
  } catch (_) {
    return null;
  }
}

/// Creates (or reuses) the booking's share link and opens the share sheet with it.
Future<void> shareVisitStatus(BuildContext context, {required String bookingId, TrustApi? api, ShareText? share}) async {
  final l10n = context.l10n;
  final messenger = ScaffoldMessenger.of(context);
  try {
    final link = await (api ?? sl<TrustApi>()).share(bookingId);
    await (share ?? systemShare)(l10n.shareVisitText(link.url));
  } catch (_) {
    messenger.showSnackBar(SnackBar(content: Text(l10n.shareVisitFailed)));
  }
}

/// Asks first, alerts the safety team with the position if there is one, then offers to call 112.
/// When the alert cannot be sent, the call is still offered, more urgently.
Future<void> sendSos(
  BuildContext context, {
  required String bookingId,
  TrustApi? api,
  CurrentFix? location,
  OpenUri? openUri,
}) async {
  final l10n = context.l10n;
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      icon: Icon(Icons.sos, color: dialogContext.colors.error, size: 36),
      title: Text(l10n.sosTitle),
      content: Text(l10n.sosBody),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(l10n.notNow)),
        FilledButton(
          key: const ValueKey('sos-confirm'),
          style: FilledButton.styleFrom(
            backgroundColor: dialogContext.colors.error,
            foregroundColor: dialogContext.colors.onError,
          ),
          onPressed: () => Navigator.pop(dialogContext, true),
          child: Text(l10n.sosSend),
        ),
      ],
    ),
  );
  if (confirmed != true || !context.mounted) return;
  var number = SosResult.defaultEmergencyNumber;
  var sent = false;
  try {
    final fix = await (location ?? permittedFix)();
    final result = await (api ?? sl<TrustApi>()).sos(bookingId, latitude: fix?.latitude, longitude: fix?.longitude);
    number = result.emergencyNumber;
    sent = true;
  } catch (_) {
    sent = false;
  }
  if (!context.mounted) return;
  await showDialog<void>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      icon: Icon(sent ? Icons.check_circle_outline : Icons.warning_amber_rounded,
          color: sent ? dialogContext.palette.success : dialogContext.colors.error, size: 36),
      content: Text(sent ? l10n.sosSent : l10n.sosFailed, style: AppTextStyles.body1),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogContext), child: Text(l10n.close)),
        FilledButton.icon(
          key: const ValueKey('sos-call'),
          style: FilledButton.styleFrom(
            backgroundColor: dialogContext.colors.error,
            foregroundColor: dialogContext.colors.onError,
          ),
          icon: const Icon(Icons.call),
          label: Text(l10n.sosCall(number)),
          onPressed: () {
            Navigator.pop(dialogContext);
            (openUri ?? openExternalUri)(Uri(scheme: 'tel', path: number));
          },
        ),
      ],
    ),
  );
}

/// The red SOS button for an active home visit.
class SosButton extends StatelessWidget {
  final String bookingId;
  final TrustApi? api;
  final CurrentFix? location;
  final OpenUri? openUri;

  const SosButton({super.key, required this.bookingId, this.api, this.location, this.openUri});

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
        key: ValueKey('sos-$bookingId'),
        style: OutlinedButton.styleFrom(
          foregroundColor: context.colors.error,
          side: BorderSide(color: context.colors.error),
        ),
        icon: const Icon(Icons.sos),
        label: Text(context.l10n.sosButton),
        onPressed: () => sendSos(context, bookingId: bookingId, api: api, location: location, openUri: openUri),
      );
}
