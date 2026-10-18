import 'package:flutter/material.dart';

/// The home shell's tabs that other screens can send the customer to.
enum ShellTab { home, services, bookings, profile }

/// Lets a screen pushed over the home shell (a booking just made, say) close itself and the screens
/// under it and switch the shell to another tab.
class ShellNavigation extends ChangeNotifier {
  ShellNavigation._();

  static final ShellNavigation instance = ShellNavigation._();

  ShellTab? _requested;

  /// The tab last asked for; the shell reads it when notified.
  ShellTab? get requested => _requested;

  /// Pops back to the shell and shows [tab].
  static void show(BuildContext context, ShellTab tab) {
    Navigator.of(context).popUntil((route) => route.isFirst);
    instance._requested = tab;
    instance.notifyListeners();
  }
}
