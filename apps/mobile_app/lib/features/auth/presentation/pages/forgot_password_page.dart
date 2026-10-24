import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/custom_text_field.dart';
import '../../../../shared/utils/validators.dart';
import '../../domain/repositories/auth_repository.dart';
import '../../../../l10n/l10n.dart';

/// Password recovery by SMS: request a code, then set a new password with it.
class ForgotPasswordPage extends StatefulWidget {
  final AuthRepository? repository;

  const ForgotPasswordPage({super.key, this.repository});

  @override
  State<ForgotPasswordPage> createState() => _ForgotPasswordPageState();
}

enum _Step { request, reset, done }

class _ForgotPasswordPageState extends State<ForgotPasswordPage> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  final _codeController = TextEditingController();
  final _passwordController = TextEditingController();
  _Step _step = _Step.request;
  bool _isLoading = false;
  bool _obscure = true;

  AuthRepository get _repository => widget.repository ?? sl<AuthRepository>();

  @override
  void dispose() {
    _phoneController.dispose();
    _codeController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: AppColors.error),
    );
  }

  Future<void> _onSubmit() async {
    if (_isLoading) return;
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() => _isLoading = true);
    final result = _step == _Step.request
        ? await _repository.forgotPassword(_phoneController.text.trim())
        : await _repository.resetPassword(
            phone: _phoneController.text.trim(),
            code: _codeController.text.trim(),
            newPassword: _passwordController.text,
          );
    if (!mounted) return;
    setState(() => _isLoading = false);
    result.fold(
      (failure) => _showError(failure.message),
      (_) => setState(() => _step = _step == _Step.request ? _Step.reset : _Step.done),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.l10n.forgotTitle)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: _step == _Step.done ? _buildSuccessView() : _buildFormView(),
      ),
    );
  }

  Widget _buildFormView() {
    final l10n = context.l10n;
    final requesting = _step == _Step.request;
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Text(l10n.resetPassword, style: AppTextStyles.heading2),
          const SizedBox(height: 8),
          Text(
            requesting
                ? l10n.forgotIntro
                : l10n.forgotEnterCode(_phoneController.text.trim()),
            style: AppTextStyles.body2.themed(context),
          ),
          const SizedBox(height: 32),
          CustomTextField(
            controller: _phoneController,
            label: l10n.loginPhoneOrEmail,
            hint: l10n.loginPhoneOrEmailHint,
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.telephoneNumber, AutofillHints.email],
            validator: Validators.phoneOrEmail,
            readOnly: !requesting,
          ),
          if (!requesting)
            TextButton(
              style: TextButton.styleFrom(padding: EdgeInsets.zero),
              onPressed: _isLoading ? null : () => setState(() => _step = _Step.request),
              child: Text(l10n.forgotDifferent),
            ),
          if (!requesting) ...[
            const SizedBox(height: 16),
            CustomTextField(
              controller: _codeController,
              label: l10n.code,
              hint: l10n.codeHint,
              keyboardType: TextInputType.number,
              autofillHints: const [AutofillHints.oneTimeCode],
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              maxLength: 6,
              validator: Validators.otp,
            ),
            const SizedBox(height: 16),
            CustomTextField(
              controller: _passwordController,
              label: l10n.newPassword,
              hint: l10n.newPasswordHint,
              helper: Validators.passwordRules,
              obscureText: _obscure,
              autofillHints: const [AutofillHints.newPassword],
              validator: Validators.password,
              suffix: IconButton(
                tooltip: _obscure ? l10n.showPassword : l10n.hidePassword,
                icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility, color: context.palette.muted),
                onPressed: () => setState(() => _obscure = !_obscure),
              ),
            ),
          ],
          const SizedBox(height: 32),
          CustomButton(
            label: requesting ? l10n.sendCode : l10n.resetPassword,
            onPressed: _isLoading ? null : _onSubmit,
            isLoading: _isLoading,
          ),
        ],
      ),
    );
  }

  Widget _buildSuccessView() {
    return Column(
      children: [
        const SizedBox(height: 48),
        Icon(Icons.check_circle_outline, size: 80, color: context.palette.success),
        const SizedBox(height: 24),
        Text(context.l10n.passwordChanged, style: AppTextStyles.heading2),
        const SizedBox(height: 8),
        Text(
          context.l10n.passwordChangedBody,
          style: AppTextStyles.body2.themed(context),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 32),
        CustomButton(label: context.l10n.backToLogin, onPressed: () => Navigator.pop(context)),
      ],
    );
  }
}
