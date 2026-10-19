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
      appBar: AppBar(title: const Text('Forgot Password')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: _step == _Step.done ? _buildSuccessView() : _buildFormView(),
      ),
    );
  }

  Widget _buildFormView() {
    final requesting = _step == _Step.request;
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          const Text('Reset Password', style: AppTextStyles.heading2),
          const SizedBox(height: 8),
          Text(
            requesting
                ? 'Enter the phone number or email on your account and we\'ll send you a code.'
                : 'Enter the code we sent to ${_phoneController.text.trim()} and choose a new password.',
            style: AppTextStyles.body2.themed(context),
          ),
          const SizedBox(height: 32),
          CustomTextField(
            controller: _phoneController,
            label: 'Phone or email',
            hint: '98765 43210 or you@example.com',
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.telephoneNumber, AutofillHints.email],
            validator: Validators.phoneOrEmail,
            readOnly: !requesting,
          ),
          if (!requesting)
            TextButton(
              style: TextButton.styleFrom(padding: EdgeInsets.zero),
              onPressed: _isLoading ? null : () => setState(() => _step = _Step.request),
              child: const Text('Use a different phone or email'),
            ),
          if (!requesting) ...[
            const SizedBox(height: 16),
            CustomTextField(
              controller: _codeController,
              label: 'Code',
              hint: '6-digit code',
              keyboardType: TextInputType.number,
              autofillHints: const [AutofillHints.oneTimeCode],
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              maxLength: 6,
              validator: Validators.otp,
            ),
            const SizedBox(height: 16),
            CustomTextField(
              controller: _passwordController,
              label: 'New Password',
              hint: 'Choose a new password',
              helper: Validators.passwordRules,
              obscureText: _obscure,
              autofillHints: const [AutofillHints.newPassword],
              validator: Validators.password,
              suffix: IconButton(
                tooltip: _obscure ? 'Show password' : 'Hide password',
                icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility, color: context.palette.muted),
                onPressed: () => setState(() => _obscure = !_obscure),
              ),
            ),
          ],
          const SizedBox(height: 32),
          CustomButton(
            label: requesting ? 'Send Code' : 'Reset Password',
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
        const Text('Password Changed', style: AppTextStyles.heading2),
        const SizedBox(height: 8),
        Text(
          'Sign in with your new password. Other devices have been signed out.',
          style: AppTextStyles.body2.themed(context),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 32),
        CustomButton(label: 'Back to Login', onPressed: () => Navigator.pop(context)),
      ],
    );
  }
}
