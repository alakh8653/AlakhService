import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/custom_text_field.dart';
import '../../../../shared/utils/validators.dart';
import '../../../directions/presentation/how_to_get_there_sheet.dart' show LinkOpener, openExternally;
import '../../../legal/data/legal_api.dart';
import '../bloc/auth_bloc.dart';
import '../bloc/auth_event.dart';
import '../bloc/auth_state.dart';
import 'login_page.dart' show isTopRoute;
import 'otp_verification_page.dart';
import '../../../../l10n/l10n.dart';

class RegisterPage extends StatefulWidget {
  /// Where the current Terms version and links come from; the build's own when left out.
  final LegalApi? legalApi;
  final LinkOpener? open;

  const RegisterPage({super.key, this.legalApi, this.open});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _acceptedTerms = false;
  LegalInfo _legal = LegalInfo.fallback;

  @override
  void initState() {
    super.initState();
    final api = widget.legalApi ?? (sl.isRegistered<LegalApi>() ? sl<LegalApi>() : null);
    api?.current().then((info) {
      if (mounted) setState(() => _legal = info);
    });
  }

  void _openLink(String url) => (widget.open ?? openExternally)(Uri.parse(url)).catchError((Object _) => false);

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _onRegister() {
    if (context.read<AuthBloc>().state is AuthLoading) return;
    if (_formKey.currentState?.validate() ?? false) {
      context.read<AuthBloc>().add(
            RegisterRequested(
              name: _nameController.text.trim(),
              phone: _phoneController.text.trim(),
              password: _passwordController.text,
              role: AppConstants.roleUser,
              acceptedTermsVersion: _legal.termsVersion,
            ),
          );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.registerTitle)),
      body: BlocListener<AuthBloc, AuthState>(
        listenWhen: (_, __) => isTopRoute(context),
        listener: (context, state) {
          if (state is OtpRequired && state.purpose == 'registration') {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(
                builder: (_) => OtpVerificationPage(phone: state.phone),
              ),
            );
          } else if (state is AuthError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          }
        },
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.registerHeading, style: AppTextStyles.heading2),
                const SizedBox(height: 8),
                Text(l10n.registerSubtitle,
                    style: AppTextStyles.body2.themed(context)),
                const SizedBox(height: 32),
                CustomTextField(
                  controller: _nameController,
                  label: l10n.fullName,
                  hint: l10n.registerNameHint,
                  textCapitalization: TextCapitalization.words,
                  textInputAction: TextInputAction.next,
                  autofillHints: const [AutofillHints.name],
                  validator: Validators.name,
                ),
                const SizedBox(height: 16),
                CustomTextField(
                  controller: _phoneController,
                  label: l10n.mobileNumber,
                  hint: '98765 43210',
                  prefixText: '+91 ',
                  keyboardType: TextInputType.phone,
                  textInputAction: TextInputAction.next,
                  autofillHints: const [AutofillHints.telephoneNumberNational],
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  maxLength: 10,
                  validator: Validators.indianMobile,
                ),
                const SizedBox(height: 16),
                CustomTextField(
                  controller: _passwordController,
                  label: l10n.password,
                  hint: l10n.registerPasswordHint,
                  helper: Validators.passwordRules,
                  obscureText: _obscurePassword,
                  textInputAction: TextInputAction.done,
                  autofillHints: const [AutofillHints.newPassword],
                  validator: Validators.password,
                  onSubmitted: (_) => _onRegister(),
                  suffix: IconButton(
                    tooltip: _obscurePassword ? l10n.showPassword : l10n.hidePassword,
                    icon: Icon(
                      _obscurePassword
                          ? Icons.visibility_off
                          : Icons.visibility,
                      color: context.palette.muted,
                    ),
                    onPressed: () =>
                        setState(() => _obscurePassword = !_obscurePassword),
                  ),
                ),
                const SizedBox(height: 12),
                // Provider accounts are set up by a shop or an admin, so sign-up is for customers.
                Text(
                  l10n.registerCodeNote,
                  style: AppTextStyles.caption.themed(context),
                ),
                const SizedBox(height: 16),
                FormField<bool>(
                  initialValue: _acceptedTerms,
                  validator: (_) => _acceptedTerms ? null : l10n.termsRequired,
                  builder: (field) => Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Checkbox(
                            value: _acceptedTerms,
                            onChanged: (value) {
                              setState(() => _acceptedTerms = value ?? false);
                              field.didChange(value);
                            },
                          ),
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.only(top: 4),
                              child: Wrap(
                                crossAxisAlignment: WrapCrossAlignment.center,
                                children: [
                                  Text(l10n.termsAgree, style: AppTextStyles.body2.themed(context)),
                                  _LinkButton(label: l10n.termsOfService, onTap: () => _openLink(_legal.termsUrl)),
                                  Text(l10n.termsAnd, style: AppTextStyles.body2.themed(context)),
                                  _LinkButton(label: l10n.privacyPolicy, onTap: () => _openLink(_legal.privacyUrl)),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                      if (field.hasError)
                        Padding(
                          padding: const EdgeInsets.only(left: 12),
                          child: Text(
                            field.errorText!,
                            style: AppTextStyles.caption.copyWith(color: context.colors.error),
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                BlocBuilder<AuthBloc, AuthState>(
                  builder: (context, state) {
                    return CustomButton(
                      label: l10n.registerButton,
                      onPressed: state is AuthLoading ? null : _onRegister,
                      isLoading: state is AuthLoading,
                    );
                  },
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: Wrap(
                    alignment: WrapAlignment.center,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(l10n.registerHaveAccount, style: AppTextStyles.body2.themed(context)),
                      TextButton(onPressed: () => Navigator.pop(context), child: Text(l10n.loginButton)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// A compact text link inside a sentence.
class _LinkButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _LinkButton({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) => TextButton(
        onPressed: onTap,
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          minimumSize: const Size(0, 36),
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
        child: Text(label),
      );
}
