import 'package:flutter/material.dart';

import '../constants/app_constants.dart';

/// General-purpose helper utilities.
abstract class AppHelpers {
  /// Shows a themed [SnackBar].
  static void showSnackBar(
    BuildContext context,
    String message, {
    bool isError = false,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.red.shade700 : Colors.green.shade700,
        duration: const Duration(milliseconds: AppConstants.snackBarDurationMs),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    );
  }

  /// Converts a server [amount] in cents to a display string like `"$12.50"`.
  static String formatCurrency(num amount, {String symbol = AppConstants.currencySymbol}) {
    return '$symbol${(amount / 100).toStringAsFixed(2)}';
  }

  /// Capitalises the first letter of every word in [text].
  static String toTitleCase(String text) {
    return text
        .split(' ')
        .map((word) => word.isEmpty ? '' : '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}')
        .join(' ');
  }

  /// Returns `"** ** 1234"` masked card number.
  static String maskCardNumber(String number) {
    if (number.length < 4) return number;
    return '**** **** **** ${number.substring(number.length - 4)}';
  }

  /// Dismisses the current keyboard focus.
  static void dismissKeyboard(BuildContext context) {
    FocusScope.of(context).unfocus();
  }

  /// Safely navigates back if possible.
  static void safeGoBack(BuildContext context) {
    if (Navigator.of(context).canPop()) Navigator.of(context).pop();
  }

  /// Converts a list of strings into a comma-separated sentence.
  static String joinWithAnd(List<String> items) {
    if (items.isEmpty) return '';
    if (items.length == 1) return items.first;
    return '${items.take(items.length - 1).join(', ')} and ${items.last}';
  }
}
