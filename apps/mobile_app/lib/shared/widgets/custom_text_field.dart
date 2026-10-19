import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/theme/app_text_styles.dart';
import '../../core/theme/app_theme.dart';

class CustomTextField extends StatelessWidget {
  final TextEditingController? controller;
  final String? label;
  final String? hint;

  /// Guidance shown under the field until it has an error (e.g. password rules).
  final String? helper;
  final String? Function(String?)? validator;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final TextCapitalization textCapitalization;
  final Iterable<String>? autofillHints;
  final List<TextInputFormatter>? inputFormatters;
  final int? maxLength;
  final bool obscureText;
  final bool readOnly;
  final int? maxLines;
  final Widget? suffix;
  final Widget? prefix;

  /// Fixed text before the input, e.g. "+91 ".
  final String? prefixText;
  final void Function(String)? onChanged;
  final void Function(String)? onSubmitted;

  const CustomTextField({
    super.key,
    this.controller,
    this.label,
    this.hint,
    this.helper,
    this.validator,
    this.keyboardType,
    this.textInputAction,
    this.textCapitalization = TextCapitalization.none,
    this.autofillHints,
    this.inputFormatters,
    this.maxLength,
    this.obscureText = false,
    this.readOnly = false,
    this.maxLines = 1,
    this.suffix,
    this.prefix,
    this.prefixText,
    this.onChanged,
    this.onSubmitted,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (label != null) ...[
          Text(label!, style: AppTextStyles.subtitle2.themed(context)),
          const SizedBox(height: 6),
        ],
        TextFormField(
          controller: controller,
          validator: validator,
          keyboardType: keyboardType,
          textInputAction: textInputAction,
          textCapitalization: textCapitalization,
          autofillHints: readOnly ? null : autofillHints,
          inputFormatters: inputFormatters,
          maxLength: maxLength,
          obscureText: obscureText,
          readOnly: readOnly,
          maxLines: obscureText ? 1 : maxLines,
          onChanged: onChanged,
          onFieldSubmitted: onSubmitted,
          style: AppTextStyles.body1,
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: AppTextStyles.body2.themed(context),
            helperText: helper,
            helperMaxLines: 2,
            errorMaxLines: 2,
            counterText: maxLength == null ? null : '',
            suffixIcon: suffix,
            // Shown always (prefixText would only appear once the field is focused), so "+91" is
            // visible before typing.
            prefixIcon: prefix ??
                (prefixText == null
                    ? null
                    : Padding(
                        padding: const EdgeInsets.only(left: 16, right: 4),
                        child: Text(prefixText!.trim(), style: AppTextStyles.body1),
                      )),
            prefixIconConstraints: prefixText == null ? null : const BoxConstraints(minWidth: 0, minHeight: 0),
          ),
        ),
      ],
    );
  }
}
