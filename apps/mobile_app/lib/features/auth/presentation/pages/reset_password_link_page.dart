import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/utils/validators.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/custom_text_field.dart';
import '../../data/datasources/auth_remote_datasource.dart';

/// Choosing a new password from an emailed reset link (https://{domain}/reset-password?token=...).
class ResetPasswordLinkPage extends StatefulWidget {
  final String token;
  final AuthRemoteDataSource? auth;

  const ResetPasswordLinkPage({super.key, required this.token, this.auth});

  @override
  State<ResetPasswordLinkPage> createState() => _ResetPasswordLinkPageState();
}

class _ResetPasswordLinkPageState extends State<ResetPasswordLinkPage> {
  final _formKey = GlobalKey<FormState>();
  final _password = TextEditingController();
  bool _obscure = true;
  bool _saving = false;
  bool _done = false;

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_saving || !(_formKey.currentState?.validate() ?? false)) return;
    setState(() => _saving = true);
    try {
      await (widget.auth ?? sl<AuthRemoteDataSource>()).resetPassword(resetToken: widget.token, newPassword: _password.text);
      if (mounted) setState(() => _done = true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.resetPassword)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: _done
            ? Column(
                children: [
                  const SizedBox(height: 32),
                  Icon(Icons.check_circle, size: 72, color: context.palette.success),
                  const SizedBox(height: 16),
                  Text(l10n.passwordChanged, style: AppTextStyles.heading3, textAlign: TextAlign.center),
                  const SizedBox(height: 8),
                  Text(l10n.passwordChangedBody, style: AppTextStyles.body2.themed(context), textAlign: TextAlign.center),
                  const SizedBox(height: 24),
                  CustomButton(label: l10n.backToLogin, onPressed: () => Navigator.of(context).pop()),
                ],
              )
            : Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    CustomTextField(
                      controller: _password,
                      label: l10n.newPassword,
                      hint: l10n.newPasswordHint,
                      helper: Validators.passwordRules,
                      obscureText: _obscure,
                      autofillHints: const [AutofillHints.newPassword],
                      validator: Validators.password,
                      onSubmitted: (_) => _submit(),
                      suffix: IconButton(
                        tooltip: _obscure ? l10n.showPassword : l10n.hidePassword,
                        icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                    const SizedBox(height: 24),
                    CustomButton(label: l10n.resetPassword, isLoading: _saving, onPressed: _saving ? null : _submit),
                  ],
                ),
              ),
      ),
    );
  }
}
