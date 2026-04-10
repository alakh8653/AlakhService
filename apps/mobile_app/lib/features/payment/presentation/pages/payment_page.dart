import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';

class PaymentPage extends StatefulWidget {
  final double amount;
  final String bookingId;

  const PaymentPage({
    super.key,
    required this.amount,
    required this.bookingId,
  });

  @override
  State<PaymentPage> createState() => _PaymentPageState();
}

class _PaymentPageState extends State<PaymentPage> {
  String _selectedMethod = 'upi';
  bool _isProcessing = false;

  static const List<_PaymentMethod> _methods = [
    _PaymentMethod(id: 'upi', label: 'UPI', icon: Icons.account_balance),
    _PaymentMethod(id: 'card', label: 'Credit/Debit Card', icon: Icons.credit_card),
    _PaymentMethod(id: 'netbanking', label: 'Net Banking', icon: Icons.computer),
    _PaymentMethod(id: 'cod', label: 'Cash on Delivery', icon: Icons.money),
  ];

  Future<void> _onPay() async {
    setState(() => _isProcessing = true);
    // Simulate payment processing
    await Future.delayed(const Duration(seconds: 2));
    if (mounted) {
      setState(() => _isProcessing = false);
      _showSuccessDialog();
    }
  }

  void _showSuccessDialog() {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        title: const Text('Payment Successful'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.check_circle,
              color: AppColors.success,
              size: 64,
            ),
            const SizedBox(height: 12),
            Text(
              '₹${widget.amount.toStringAsFixed(2)} paid successfully',
              style: AppTextStyles.body1,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              Navigator.pop(context);
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
            Text('Payment Method', style: AppTextStyles.subtitle1),
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
                        color: isSelected
                            ? AppColors.primaryLight
                            : AppColors.surface,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isSelected
                              ? AppColors.primary
                              : AppColors.border,
                          width: isSelected ? 2 : 1,
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            method.icon,
                            color: isSelected
                                ? AppColors.primary
                                : AppColors.textSecondary,
                          ),
                          const SizedBox(width: 12),
                          Text(method.label, style: AppTextStyles.body1),
                          const Spacer(),
                          if (isSelected)
                            const Icon(
                              Icons.check_circle,
                              color: AppColors.primary,
                            ),
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
              Text('Total Amount', style: AppTextStyles.body2),
              Text(
                '₹${amount.toStringAsFixed(2)}',
                style: AppTextStyles.heading2.copyWith(color: AppColors.primary),
              ),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('Booking ID', style: AppTextStyles.caption),
              Text(
                '#${bookingId.substring(0, 8).toUpperCase()}',
                style: AppTextStyles.subtitle2,
              ),
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

  const _PaymentMethod({
    required this.id,
    required this.label,
    required this.icon,
  });
}
