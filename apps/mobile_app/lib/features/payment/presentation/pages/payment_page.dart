import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../l10n/l10n.dart';
import '../../data/payment_api.dart';
import '../../data/razorpay_checkout.dart';

/// Pays for a booking. The server charges the booking's own price, whatever [amount] shows here.
///
/// Online methods open Razorpay's checkout for the order the server created, then the server
/// verifies Razorpay's signature before the payment counts. Cash is settled with the provider.
class PaymentPage extends StatefulWidget {
  final double amount;
  final String bookingId;

  /// Shown so the customer knows what they are paying for.
  final String bookingNumber;
  final String? serviceName;
  final PaymentApi? paymentApi;
  final CheckoutLauncher? checkoutLauncher;

  const PaymentPage({
    super.key,
    required this.amount,
    required this.bookingId,
    this.bookingNumber = '',
    this.serviceName,
    this.paymentApi,
    this.checkoutLauncher,
  });

  @override
  State<PaymentPage> createState() => _PaymentPageState();
}

class _PaymentPageState extends State<PaymentPage> {
  late final PaymentApi _api = widget.paymentApi ?? sl<PaymentApi>();
  late final CheckoutLauncher _checkout = widget.checkoutLauncher ?? RazorpayCheckoutLauncher();
  // One key per attempt on this screen, so a retried tap never creates a second payment.
  final String _idempotencyKey = PaymentApi.newIdempotencyKey();
  String _selectedMethod = 'upi';
  bool _isProcessing = false;

  /// The booking number customers see elsewhere, or a short form of the id.
  String get _reference => widget.bookingNumber.isNotEmpty ? widget.bookingNumber : _shortId(widget.bookingId);

  static List<_PaymentMethod> _methodsIn(AppLocalizations l10n) => [
        _PaymentMethod(id: 'upi', label: l10n.payMethodUpi, icon: Icons.account_balance, hint: l10n.payMethodUpiHint),
        _PaymentMethod(id: 'card', label: l10n.payMethodCard, icon: Icons.credit_card),
        _PaymentMethod(id: 'netbanking', label: l10n.payMethodNetbanking, icon: Icons.computer),
        _PaymentMethod(id: 'cash', label: l10n.payMethodCash, icon: Icons.money, hint: l10n.payMethodCashHint),
      ];

  void _showMessage(String message, {bool error = true}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: error ? AppColors.error : null),
    );
  }

  Future<void> _onPay() async {
    if (_isProcessing) return;
    setState(() => _isProcessing = true);
    try {
      var result = await _api.payForBooking(
        bookingId: widget.bookingId,
        method: _selectedMethod,
        idempotencyKey: _idempotencyKey,
      );
      final checkout = result.checkout;
      if (checkout != null) {
        final outcome = await _checkout.open(checkout, description: 'Booking #$_reference');
        if (!mounted) return;
        switch (outcome) {
          case CheckoutPaid():
            result = await _api.verify(
              paymentId: result.id,
              orderId: outcome.orderId,
              gatewayPaymentId: outcome.paymentId,
              signature: outcome.signature,
            );
          case CheckoutCancelled():
            setState(() => _isProcessing = false);
            return _showMessage(context.l10n.paymentCancelled, error: false);
          case CheckoutFailed(:final message):
            setState(() => _isProcessing = false);
            return _showMessage(message);
        }
      }
      if (!mounted) return;
      setState(() => _isProcessing = false);
      _showResult(result);
    } catch (e) {
      if (!mounted) return;
      setState(() => _isProcessing = false);
      _showMessage(apiErrorMessage(e));
    }
  }

  void _showResult(PaymentResult result) {
    final l10n = context.l10n;
    final amount = rupees(result.amount);
    final completed = result.isCompleted;
    final message = completed
        ? l10n.paymentPaidAmount(amount)
        : _selectedMethod == 'cash'
            ? l10n.paymentCashBody(amount)
            : l10n.paymentConfirmingBody(amount);
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: Text(completed
            ? l10n.paymentSuccessful
            : _selectedMethod == 'cash'
                ? l10n.paymentCashNoted
                : l10n.paymentRecorded),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              completed ? Icons.check_circle : Icons.hourglass_top,
              color: completed ? context.palette.success : context.colors.primary,
              size: 64,
            ),
            const SizedBox(height: 12),
            Text(message, style: AppTextStyles.body1, textAlign: TextAlign.center),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              Navigator.pop(context, true);
            },
            child: Text(l10n.done),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final methods = _methodsIn(l10n);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.paymentTitle)),
      // Everything scrolls, and the Pay button stays at the bottom: on a small phone with large
      // text the methods no longer squeeze the button off screen.
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_selectedMethod != 'cash')
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.lock_outline, size: 14, color: context.palette.muted),
                      const SizedBox(width: 4),
                      Flexible(
                          child: Text(l10n.paymentSecured,
                              style: AppTextStyles.caption.themed(context))),
                    ],
                  ),
                ),
              CustomButton(
                label: _selectedMethod == 'cash'
                    ? l10n.payInCashButton(rupees(widget.amount))
                    : l10n.payAmount(rupees(widget.amount)),
                onPressed: _isProcessing ? null : _onPay,
                isLoading: _isProcessing,
              ),
            ],
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          _AmountSummaryCard(amount: widget.amount, reference: _reference, serviceName: widget.serviceName),
          const SizedBox(height: 24),
          Semantics(header: true, child: Text(l10n.paymentMethod, style: AppTextStyles.subtitle1)),
          const SizedBox(height: 12),
          for (var index = 0; index < methods.length; index++)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Builder(builder: (context) {
                final method = methods[index];
                final isSelected = _selectedMethod == method.id;
                return Semantics(
                  inMutuallyExclusiveGroup: true,
                  selected: isSelected,
                  child: InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: _isProcessing ? null : () => setState(() => _selectedMethod = method.id),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: isSelected ? context.colors.primaryContainer : context.colors.surface,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isSelected ? context.colors.primary : context.colors.outlineVariant,
                          width: isSelected ? 2 : 1,
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            method.icon,
                            color: isSelected ? context.colors.primary : context.palette.muted,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(method.label, style: AppTextStyles.body1),
                                if (method.hint != null) Text(method.hint!, style: AppTextStyles.caption.themed(context)),
                              ],
                            ),
                          ),
                          Icon(
                            isSelected ? Icons.radio_button_checked : Icons.radio_button_off,
                            color: isSelected ? context.colors.primary : context.palette.muted,
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }),
            ),
        ],
      ),
    );
  }
}

class _AmountSummaryCard extends StatelessWidget {
  final double amount;
  final String reference;
  final String? serviceName;

  const _AmountSummaryCard({required this.amount, required this.reference, this.serviceName});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.primaryContainer,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(serviceName ?? context.l10n.amountToPay,
                    style: AppTextStyles.body2.themed(context), maxLines: 2, overflow: TextOverflow.ellipsis),
                Text(
                  rupees(amount),
                  style: AppTextStyles.heading2.copyWith(color: context.colors.primary),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(context.l10n.bookingLabel, style: AppTextStyles.caption.themed(context)),
              Text('#$reference', style: AppTextStyles.subtitle2.themed(context)),
            ],
          ),
        ],
      ),
    );
  }
}

String _shortId(String id) => (id.length > 8 ? id.substring(0, 8) : id).toUpperCase();

class _PaymentMethod {
  final String id;
  final String label;
  final IconData icon;
  final String? hint;

  const _PaymentMethod({required this.id, required this.label, required this.icon, this.hint});
}
