import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

/// General-purpose helper utilities.
class AppHelpers {
  AppHelpers._();

  static final NumberFormat _inrFormat = NumberFormat.currency(
    locale: 'en_IN',
    symbol: '₹',
    decimalDigits: 0,
  );

  static final NumberFormat _inrFormatDecimal = NumberFormat.currency(
    locale: 'en_IN',
    symbol: '₹',
    decimalDigits: 2,
  );

  /// Formats an amount in Indian Rupees, e.g. "₹1,499".
  static String formatCurrency(double amount) => _inrFormat.format(amount);

  /// Formats with two decimal places, e.g. "₹1,499.00".
  static String formatCurrencyDecimal(double amount) =>
      _inrFormatDecimal.format(amount);

  /// Capitalises the first letter of each word.
  static String toTitleCase(String text) {
    return text
        .split(' ')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }

  /// Converts a snake_case or kebab-case string to a human-readable label.
  static String humanize(String text) =>
      toTitleCase(text.replaceAll(RegExp(r'[_\-]'), ' '));

  /// Returns initials from a full name, e.g. "John Doe" → "JD".
  static String initials(String name) {
    final parts = name.trim().split(' ');
    if (parts.isEmpty) return '';
    if (parts.length == 1) return parts[0][0].toUpperCase();
    return '${parts.first[0]}${parts.last[0]}'.toUpperCase();
  }

  /// Truncates a string and appends ellipsis if it exceeds [maxLength].
  static String truncate(String text, int maxLength) {
    if (text.length <= maxLength) return text;
    return '${text.substring(0, maxLength)}...';
  }

  /// Shows a brief SnackBar message.
  static void showSnackBar(
    BuildContext context,
    String message, {
    bool isError = false,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor:
            isError ? const Color(0xFFEF4444) : const Color(0xFF10B981),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  /// Returns the colour that corresponds to a booking status string.
  static Color statusColor(String status) {
    return switch (status.toLowerCase()) {
      'confirmed' => const Color(0xFF10B981),
      'pending' => const Color(0xFFF59E0B),
      'cancelled' => const Color(0xFFEF4444),
      'completed' => const Color(0xFF3B82F6),
      _ => const Color(0xFF6B7280),
    };
  }
}
