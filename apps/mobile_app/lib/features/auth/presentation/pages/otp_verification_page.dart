import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../bloc/auth_bloc.dart';
import '../bloc/auth_event.dart';
import '../bloc/auth_state.dart';

/// Asks for the one-time code sent to [phone] (a phone number or email), to confirm a new
/// account ('registration') or to sign in without a password ('login').
///
/// One field rather than a box per digit, so the code can be pasted or filled in from the SMS by
/// the keyboard; it submits itself once all digits are in.
class OtpVerificationPage extends StatefulWidget {
  final String phone;
  final String purpose;

  /// How long before "Resend" is offered again.
  final Duration resendAfter;

  const OtpVerificationPage({
    super.key,
    required this.phone,
    this.purpose = 'registration',
    this.resendAfter = const Duration(seconds: 30),
  });

  @override
  State<OtpVerificationPage> createState() => _OtpVerificationPageState();
}

class _OtpVerificationPageState extends State<OtpVerificationPage> {
  final _controller = TextEditingController();
  Timer? _ticker;
  late int _secondsLeft;

  bool get _complete => _controller.text.length == AppConstants.otpLength;

  @override
  void initState() {
    super.initState();
    _startCountdown();
  }

  void _startCountdown() {
    _ticker?.cancel();
    setState(() => _secondsLeft = widget.resendAfter.inSeconds);
    _ticker = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return t.cancel();
      setState(() => _secondsLeft--);
      if (_secondsLeft <= 0) t.cancel();
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onVerify() {
    if (!_complete || context.read<AuthBloc>().state is AuthLoading) return;
    context.read<AuthBloc>().add(
          OtpVerificationRequested(phone: widget.phone, otp: _controller.text, purpose: widget.purpose),
        );
  }

  void _resend() {
    _controller.clear();
    context.read<AuthBloc>().add(ResendOtpRequested(widget.phone, purpose: widget.purpose));
    _startCountdown();
  }

  @override
  Widget build(BuildContext context) {
    final where = widget.phone.contains('@') ? 'email' : 'phone';
    return Scaffold(
      appBar: AppBar(title: Text(widget.purpose == 'login' ? 'Login with OTP' : 'Verify your $where')),
      body: BlocListener<AuthBloc, AuthState>(
        listenWhen: (_, __) => ModalRoute.of(context)?.isCurrent ?? true,
        listener: (context, state) {
          if (state is AuthError) {
            _controller.clear();
            setState(() {});
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          } else if (state is OtpResent) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('A new code is on its way')),
            );
          }
        },
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 24),
              Semantics(header: true, child: const Text('Enter the code', style: AppTextStyles.heading2)),
              const SizedBox(height: 8),
              Text(
                'We sent a ${AppConstants.otpLength}-digit code to ${widget.phone}.',
                style: AppTextStyles.body2.themed(context),
              ),
              TextButton(
                style: TextButton.styleFrom(padding: EdgeInsets.zero),
                onPressed: () => Navigator.pop(context),
                child: Text('Wrong $where? Change it'),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _controller,
                autofocus: true,
                keyboardType: TextInputType.number,
                textAlign: TextAlign.center,
                maxLength: AppConstants.otpLength,
                autofillHints: const [AutofillHints.oneTimeCode],
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                style: AppTextStyles.heading2.copyWith(letterSpacing: 12),
                decoration: const InputDecoration(
                  counterText: '',
                  hintText: '••••••',
                  labelText: 'One-time code',
                  floatingLabelBehavior: FloatingLabelBehavior.never,
                ),
                onChanged: (_) {
                  setState(() {});
                  if (_complete) _onVerify();
                },
                onSubmitted: (_) => _onVerify(),
              ),
              const SizedBox(height: 32),
              BlocBuilder<AuthBloc, AuthState>(
                builder: (context, state) {
                  return CustomButton(
                    label: widget.purpose == 'login' ? 'Verify and login' : 'Verify',
                    onPressed: (_complete && state is! AuthLoading) ? _onVerify : null,
                    isLoading: state is AuthLoading,
                  );
                },
              ),
              const SizedBox(height: 16),
              Center(
                child: _secondsLeft > 0
                    ? Text(
                        "Didn't get it? You can resend in ${_secondsLeft}s",
                        style: AppTextStyles.body2.themed(context),
                      )
                    : TextButton(
                        onPressed: _resend,
                        child: const Text("Didn't get it? Resend code"),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
