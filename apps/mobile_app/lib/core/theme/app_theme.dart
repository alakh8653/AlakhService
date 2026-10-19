import 'package:flutter/material.dart';
import 'app_colors.dart';
import 'app_text_styles.dart';

/// Colours the colour scheme has no role for, in versions that read on the theme's surface: secondary
/// (muted) text and icons, and green, amber and blue status text. Read with [AppPalette.of].
@immutable
class AppPalette extends ThemeExtension<AppPalette> {
  final Color muted;
  final Color success;
  final Color warning;
  final Color info;

  const AppPalette({required this.muted, required this.success, required this.warning, required this.info});

  static const light = AppPalette(
    muted: AppColors.textSecondary,
    success: AppColors.success,
    warning: AppColors.warning,
    info: AppColors.info,
  );
  static const dark = AppPalette(
    muted: AppColors.textSecondaryDark,
    success: AppColors.successOnDark,
    warning: AppColors.warningOnDark,
    info: AppColors.infoOnDark,
  );

  /// The palette of [context]'s theme; the light one under a theme without it (a bare test app).
  static AppPalette of(BuildContext context) => Theme.of(context).extension<AppPalette>() ?? light;

  @override
  AppPalette copyWith({Color? muted, Color? success, Color? warning, Color? info}) => AppPalette(
        muted: muted ?? this.muted,
        success: success ?? this.success,
        warning: warning ?? this.warning,
        info: info ?? this.info,
      );

  @override
  AppPalette lerp(AppPalette? other, double t) => other == null
      ? this
      : AppPalette(
          muted: Color.lerp(muted, other.muted, t)!,
          success: Color.lerp(success, other.success, t)!,
          warning: Color.lerp(warning, other.warning, t)!,
          info: Color.lerp(info, other.info, t)!,
        );
}

class AppTheme {
  AppTheme._();

  static const ColorScheme _light = ColorScheme.light(
    primary: AppColors.primary,
    secondary: AppColors.secondary,
    surface: AppColors.surface,
    error: AppColors.error,
    onPrimary: AppColors.textLight,
    onSecondary: AppColors.textLight,
    onSurface: AppColors.textPrimary,
    onError: AppColors.textLight,
    // The light tint behind selected days, chips and summary cards, and the deep primary on it.
    primaryContainer: AppColors.primaryLight,
    onPrimaryContainer: AppColors.primaryDark,
    outlineVariant: AppColors.border,
  );

  static const ColorScheme _dark = ColorScheme.dark(
    primary: AppColors.primaryOnDark,
    secondary: AppColors.secondary,
    surface: AppColors.surfaceDark,
    error: AppColors.errorOnDark,
    onPrimary: AppColors.textPrimary,
    onSecondary: AppColors.textLight,
    onSurface: AppColors.textPrimaryDark,
    onError: AppColors.textPrimary,
    primaryContainer: AppColors.primaryContainerDark,
    onPrimaryContainer: AppColors.onPrimaryContainerDark,
    outlineVariant: AppColors.borderDark,
    surfaceContainerHighest: AppColors.surfaceContainerDark,
  );

  static ThemeData get lightTheme => _build(_light, background: AppColors.background, palette: AppPalette.light);

  /// The same components as [lightTheme] on dark surfaces. Filled buttons keep the brand primary
  /// with white text; text buttons, chips and links take the scheme's lighter primary.
  static ThemeData get darkTheme => _build(_dark, background: AppColors.backgroundDark, palette: AppPalette.dark);

  static ThemeData _build(ColorScheme scheme, {required Color background, required AppPalette palette}) => ThemeData(
        useMaterial3: true,
        colorScheme: scheme,
        extensions: [palette],
        scaffoldBackgroundColor: background,
        fontFamily: 'Poppins',
        appBarTheme: AppBarTheme(
          backgroundColor: scheme.surface,
          foregroundColor: scheme.onSurface,
          elevation: 0,
          centerTitle: true,
          titleTextStyle: AppTextStyles.heading3.copyWith(color: scheme.onSurface),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: AppColors.textLight,
            minimumSize: const Size(double.infinity, 52),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            textStyle: AppTextStyles.button,
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: scheme.surface,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.outlineVariant),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.outlineVariant),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.primary, width: 2),
          ),
          errorBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.error),
          ),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        ),
        cardTheme: CardThemeData(
          color: scheme.surface,
          elevation: 2,
          shadowColor: AppColors.shadow,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
        // Outlined buttons in the app's border colour instead of Material's near-black outline.
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: scheme.primary,
            side: BorderSide(color: scheme.outlineVariant),
            minimumSize: const Size(48, 48),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        // Choices (service mode, date, time slot) highlight in the brand's light tint, not the pink
        // secondary colour, so the selected label stays readable.
        chipTheme: ChipThemeData(
          backgroundColor: scheme.surface,
          selectedColor: scheme.primaryContainer,
          checkmarkColor: scheme.primary,
          side: BorderSide(color: scheme.outlineVariant),
          labelStyle: AppTextStyles.body2.copyWith(color: scheme.onSurface),
          secondaryLabelStyle:
              AppTextStyles.body2.copyWith(color: scheme.onPrimaryContainer, fontWeight: FontWeight.w600),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        // The brand primary with white, in both themes (Material 3 would use the light container tint).
        floatingActionButtonTheme: const FloatingActionButtonThemeData(
          backgroundColor: AppColors.primary,
          foregroundColor: AppColors.textLight,
        ),
        snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
        dividerTheme: DividerThemeData(color: scheme.outlineVariant, thickness: 1),
        dialogTheme: DialogThemeData(backgroundColor: scheme.surface),
      );
}

/// Shorthands for the current theme's colours in widgets: `context.colors.surface`, `context.palette.muted`.
extension AppThemeContext on BuildContext {
  ColorScheme get colors => Theme.of(this).colorScheme;
  AppPalette get palette => AppPalette.of(this);
}

/// The secondary [AppTextStyles] (body2, caption, subtitle2, overline) carry the light theme's grey;
/// `AppTextStyles.caption.themed(context)` swaps it for the current theme's muted colour.
extension ThemedTextStyle on TextStyle {
  TextStyle themed(BuildContext context) =>
      color == AppColors.textSecondary ? copyWith(color: AppPalette.of(context).muted) : this;
}
