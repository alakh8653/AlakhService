import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/app_text_styles.dart';

enum ButtonVariant { primary, secondary, outlined }

class CustomButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool isLoading;
  final ButtonVariant variant;
  final IconData? leadingIcon;
  final double? width;
  final double height;

  const CustomButton({
    super.key,
    required this.label,
    this.onPressed,
    this.isLoading = false,
    this.variant = ButtonVariant.primary,
    this.leadingIcon,
    this.width,
    this.height = 52,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width ?? double.infinity,
      height: height,
      child: switch (variant) {
        ButtonVariant.primary => ElevatedButton(
            onPressed: isLoading ? null : onPressed,
            child: _child(context),
          ),
        ButtonVariant.secondary => ElevatedButton(
            onPressed: isLoading ? null : onPressed,
            style: ElevatedButton.styleFrom(
              backgroundColor: context.colors.surface,
              foregroundColor: context.colors.primary,
              side: BorderSide(color: context.colors.primary),
            ),
            child: _child(context),
          ),
        ButtonVariant.outlined => OutlinedButton(
            onPressed: isLoading ? null : onPressed,
            child: _child(context),
          ),
      },
    );
  }

  /// AppTextStyles.button without its fixed white, so each variant's foreground colour applies
  /// (otherwise secondary and outlined buttons draw white text on a white background).
  static final TextStyle _labelStyle = TextStyle(
    fontSize: AppTextStyles.button.fontSize,
    fontWeight: AppTextStyles.button.fontWeight,
    fontFamily: AppTextStyles.button.fontFamily,
    letterSpacing: AppTextStyles.button.letterSpacing,
  );

  Widget _child(BuildContext context) => isLoading
      ? SizedBox.square(
          dimension: 24,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: variant == ButtonVariant.primary ? AppColors.textLight : context.colors.primary,
          ),
        )
      : Row(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (leadingIcon != null) ...[
              Icon(leadingIcon, size: 20),
              const SizedBox(width: 8),
            ],
            // Long labels or large system text shrink with an ellipsis instead of overflowing.
            Flexible(child: Text(label, style: _labelStyle, maxLines: 1, overflow: TextOverflow.ellipsis)),
          ],
        );
}
