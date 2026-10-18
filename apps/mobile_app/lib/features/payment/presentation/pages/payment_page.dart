import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/custom_button.dart';
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

  static const List<_PaymentMethod> _methods = [
    _PaymentMethod(id: 'upi', label: 'UPI', icon: Icons.account_balance, hint: 'GPay, PhonePe, Paytm or any UPI app'),
    _PaymentMethod(id: 'card', label: 'Credit / debit card', icon: Icons.credit_card),
    _PaymentMethod(id: 'netbanking', label: 'Net banking', icon: Icons.computer),
    _PaymentMethod(id: 'cash', label: 'Pay in cash', icon: Icons.money, hint: 'Hand it to your provider when the job is done'),
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
            return _showMessage('Payment cancelled. You have not been charged.', error: false);
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
    final amount = rupees(result.amount);
    final completed = result.isCompleted;
    final message = completed
        ? '$amount paid.'
        : _selectedMethod == 'cash'
            ? 'Pay $amount in cash to your provider when the job is done.'
            : 'Payment of $amount is being confirmed. It will show as paid shortly.';
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: Text(completed ? 'Payment successful' : _selectedMethod == 'cash' ? 'Cash payment noted' : 'Payment recorded'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              completed ? Icons.check_circle : Icons.hourglass_top,
              color: completed ? AppColors.success : AppColors.primary,
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
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _AmountSummaryCard(amount: widget.amount, reference: _reference, serviceName: widget.serviceName),
            const SizedBox(height: 24),
            const Text('Payment Method', style: AppTextStyles.subtitle1),
            const SizedBox(height: 12),
            Expanded(
              child: ListView.separated(
                itemCount: _methods.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, index) {
                  final method = _methods[index];
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
                        color: isSelected ? AppColors.primaryLight : AppColors.surface,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isSelected ? AppColors.primary : AppColors.border,
                          width: isSelected ? 2 : 1,
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            method.icon,
                            color: isSelected ? AppColors.primary : AppColors.textSecondary,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(method.label, style: AppTextStyles.body1),
                                if (method.hint != null) Text(method.hint!, style: AppTextStyles.caption),
                              ],
                            ),
                          ),
                          Icon(
                            isSelected ? Icons.radio_button_checked : Icons.radio_button_off,
                            color: isSelected ? AppColors.primary : AppColors.textSecondary,
                          ),
                        ],
                      ),
                    ),
                  ),
                  );
                },
              ),
            ),
            const SizedBox(height: 16),
            if (_selectedMethod != 'cash')
              const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.lock_outline, size: 14, color: AppColors.textSecondary),
                    SizedBox(width: 4),
                    Flexible(child: Text('Secured by Razorpay. We never see your card or UPI PIN.', style: AppTextStyles.caption)),
                  ],
                ),
              ),
            CustomButton(
              label: _selectedMethod == 'cash' ? "I'll pay ${rupees(widget.amount)} in cash" : 'Pay ${rupees(widget.amount)}',
              onPressed: _isProcessing ? null : _onPay,
              isLoading: _isProcessing,
            ),
          ],
        ),
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
        color: AppColors.primaryLight,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(serviceName ?? 'Amount to pay', style: AppTextStyles.body2, maxLines: 2, overflow: TextOverflow.ellipsis),
                Text(
                  rupees(amount),
                  style: AppTextStyles.heading2.copyWith(color: AppColors.primary),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              const Text('Booking', style: AppTextStyles.caption),
              Text('#$reference', style: AppTextStyles.subtitle2),
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
