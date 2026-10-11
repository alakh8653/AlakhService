import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../data/payment_api.dart';

/// Starts payment for a booking. The server charges the booking's own price, whatever
/// [amount] shows here.
class PaymentPage extends StatefulWidget {
  final double amount;
  final String bookingId;
  final PaymentApi? paymentApi;

  const PaymentPage({
    super.key,
    required this.amount,
    required this.bookingId,
    this.paymentApi,
  });

  @override
  State<PaymentPage> createState() => _PaymentPageState();
}

class _PaymentPageState extends State<PaymentPage> {
  late final PaymentApi _api = widget.paymentApi ?? sl<PaymentApi>();
  // One key per attempt on this screen, so a retried tap never creates a second payment.
  final String _idempotencyKey = PaymentApi.newIdempotencyKey();
  String _selectedMethod = 'upi';
  bool _isProcessing = false;

  static const List<_PaymentMethod> _methods = [
    _PaymentMethod(id: 'upi', label: 'UPI', icon: Icons.account_balance),
    _PaymentMethod(id: 'card', label: 'Credit/Debit Card', icon: Icons.credit_card),
    _PaymentMethod(id: 'netbanking', label: 'Net Banking', icon: Icons.computer),
    _PaymentMethod(id: 'cash', label: 'Pay in cash', icon: Icons.money),
  ];

  Future<void> _onPay() async {
    setState(() => _isProcessing = true);
    try {
      final result = await _api.payForBooking(
        bookingId: widget.bookingId,
        method: _selectedMethod,
        idempotencyKey: _idempotencyKey,
      );
      if (!mounted) return;
      setState(() => _isProcessing = false);
      _showResult(result);
    } catch (e) {
      if (!mounted) return;
      setState(() => _isProcessing = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
      );
    }
  }

  void _showResult(PaymentResult result) {
    final amount = '₹${result.amount.toStringAsFixed(2)}';
    final completed = result.status == 'COMPLETED';
    final message = completed
        ? '$amount paid.'
        : _selectedMethod == 'cash'
            ? 'Pay $amount in cash to your provider when the job is done.'
            : 'Payment of $amount has been started and will be confirmed '
                'once your bank or UPI app approves it.';
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: Text(completed ? 'Payment Successful' : 'Payment Recorded'),
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
            _AmountSummaryCard(amount: widget.amount, bookingId: widget.bookingId),
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
                  return GestureDetector(
                    onTap: () => setState(() => _selectedMethod = method.id),
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
                          Text(method.label, style: AppTextStyles.body1),
                          const Spacer(),
                          if (isSelected) const Icon(Icons.check_circle, color: AppColors.primary),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 16),
            CustomButton(
              label: 'Pay ₹${widget.amount.toStringAsFixed(2)}',
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
  final String bookingId;

  const _AmountSummaryCard({required this.amount, required this.bookingId});

  @override
  Widget build(BuildContext context) {
    final shortId = bookingId.length > 8 ? bookingId.substring(0, 8) : bookingId;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primaryLight,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Total Amount', style: AppTextStyles.body2),
              Text(
                '₹${amount.toStringAsFixed(2)}',
                style: AppTextStyles.heading2.copyWith(color: AppColors.primary),
              ),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              const Text('Booking ID', style: AppTextStyles.caption),
              Text('#${shortId.toUpperCase()}', style: AppTextStyles.subtitle2),
            ],
          ),
        ],
      ),
    );
  }
}

class _PaymentMethod {
  final String id;
  final String label;
  final IconData icon;

  const _PaymentMethod({required this.id, required this.label, required this.icon});
}
