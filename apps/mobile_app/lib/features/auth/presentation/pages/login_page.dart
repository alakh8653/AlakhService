import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/custom_text_field.dart';
import '../../../../shared/utils/validators.dart';
import '../bloc/auth_bloc.dart';
import '../bloc/auth_event.dart';
import '../bloc/auth_state.dart';
import 'otp_verification_page.dart';
import 'register_page.dart';
import 'forgot_password_page.dart';

/// Whether [context] belongs to the screen on top, so a screen underneath (this login screen
/// under Register, say) doesn't also react to the shared AuthBloc and repeat its messages.
bool isTopRoute(BuildContext context) => ModalRoute.of(context)?.isCurrent ?? true;

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  // Set while asking for a sign-in code, so only that button shows progress.
  bool _requestedCode = false;

  @override
  void dispose() {
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _onLogin() {
    if (context.read<AuthBloc>().state is AuthLoading) return;
    if (_formKey.currentState?.validate() ?? false) {
      FocusScope.of(context).unfocus();
      setState(() => _requestedCode = false);
      context.read<AuthBloc>().add(
            LoginRequested(
              phone: _phoneController.text.trim(),
              password: _passwordController.text,
            ),
          );
    }
  }

  /// Sign in with a one-time code instead of the password: only the phone or email is needed.
  void _onCodeLogin() {
    if (context.read<AuthBloc>().state is AuthLoading) return;
    final error = Validators.phoneOrEmail(_phoneController.text);
    if (error != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error), backgroundColor: AppColors.error));
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() => _requestedCode = true);
    context.read<AuthBloc>().add(OtpLoginRequested(_phoneController.text.trim()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocListener<AuthBloc, AuthState>(
        listenWhen: (_, __) => isTopRoute(context),
        listener: (context, state) {
          if (state is AuthError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          } else if (state is OtpRequired && state.purpose == 'login') {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => OtpVerificationPage(phone: state.phone, purpose: 'login')),
            );
          }
        },
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: AutofillGroup(
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(height: 48),
                    Semantics(header: true, child: const Text('Welcome Back', style: AppTextStyles.heading1)),
                    const SizedBox(height: 8),
                    const Text(
                      'Sign in to book, track and pay for your services',
                      style: AppTextStyles.body2,
                    ),
                    const SizedBox(height: 40),
                    CustomTextField(
                      controller: _phoneController,
                      label: 'Phone or email',
                      hint: '98765 43210 or you@example.com',
                      // Letters and @ must be typeable: a phone-only keypad can't enter an email.
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                      autofillHints: const [AutofillHints.telephoneNumber, AutofillHints.email, AutofillHints.username],
                      validator: Validators.phoneOrEmail,
                    ),
                    const SizedBox(height: 16),
                    CustomTextField(
                      controller: _passwordController,
                      label: 'Password',
                      hint: 'Enter your password',
                      obscureText: _obscurePassword,
                      textInputAction: TextInputAction.done,
                      autofillHints: const [AutofillHints.password],
                      validator: Validators.loginPassword,
                      onSubmitted: (_) => _onLogin(),
                      suffix: IconButton(
                        tooltip: _obscurePassword ? 'Show password' : 'Hide password',
                        icon: Icon(
                          _obscurePassword ? Icons.visibility_off : Icons.visibility,
                          color: AppColors.textSecondary,
                        ),
                        onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                      ),
                    ),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const ForgotPasswordPage(),
                          ),
                        ),
                        child: const Text('Forgot Password?'),
                      ),
                    ),
                    const SizedBox(height: 8),
                    BlocBuilder<AuthBloc, AuthState>(
                      builder: (context, state) {
                        final loading = state is AuthLoading;
                        return Column(
                          children: [
                            CustomButton(
                              label: 'Login',
                              onPressed: loading ? null : _onLogin,
                              isLoading: loading && !_requestedCode,
                            ),
                            const SizedBox(height: 12),
                            CustomButton(
                              label: 'Login with OTP instead',
                              variant: ButtonVariant.outlined,
                              leadingIcon: Icons.sms_outlined,
                              onPressed: loading ? null : _onCodeLogin,
                              isLoading: loading && _requestedCode,
                            ),
                          ],
                        );
                      },
                    ),
                    const SizedBox(height: 24),
                    SizedBox(
                      width: double.infinity,
                      child: Wrap(
                      alignment: WrapAlignment.center,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        const Text(
                          "Don't have an account?",
                          style: AppTextStyles.body2,
                        ),
                        TextButton(
                          onPressed: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => const RegisterPage(),
                            ),
                          ),
                          child: const Text('Register'),
                        ),
                      ],
                    ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
