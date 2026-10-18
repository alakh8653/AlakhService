import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // Primary. Deep enough for white text on it, and for it as text on white, to pass WCAG AA (5.4:1).
  static const Color primary = Color(0xFF5B52F0);
  static const Color primaryDark = Color(0xFF4B44CC);
  static const Color primaryLight = Color(0xFFEEEDFF);

  // Secondary
  static const Color secondary = Color(0xFFFF6584);
  static const Color secondaryDark = Color(0xFFCC3D5A);
  static const Color secondaryLight = Color(0xFFFFEEF2);

  // Accent
  static const Color accent = Color(0xFF2E8A5C);
  static const Color accentDark = Color(0xFF2E8A5C);
  static const Color accentLight = Color(0xFFE8F8F0);

  // Neutral
  static const Color background = Color(0xFFF8F9FA);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceDark = Color(0xFF1E1E2E);
  static const Color backgroundDark = Color(0xFF121212);

  // Text
  static const Color textPrimary = Color(0xFF1A1A2E);
  static const Color textSecondary = Color(0xFF6B7280);
  static const Color textDisabled = Color(0xFFB0B7C3);
  static const Color textLight = Color(0xFFFFFFFF);

  // Status. These are used as text (status pills, prices, messages) and as snackbar backgrounds
  // under white text, so each keeps at least 4.5:1 contrast against white.
  static const Color success = Color(0xFF047857);
  static const Color warning = Color(0xFFB45309);
  static const Color error = Color(0xFFDC2626);
  static const Color info = Color(0xFF1D4ED8);

  // Border
  static const Color border = Color(0xFFE5E7EB);
  static const Color borderDark = Color(0xFF374151);

  // Divider
  static const Color divider = Color(0xFFF3F4F6);

  // Shadow
  static const Color shadow = Color(0x1A000000);

  // Star rating
  static const Color starFilled = Color(0xFFFBBF24);
  static const Color starEmpty = Color(0xFFE5E7EB);
}
