import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../widgets/custom_button.dart';
import '../../../config/routes.dart';

class PaymentPage extends StatelessWidget {
  const PaymentPage({super.key, required this.bookingId});
  final String bookingId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(Icons.payment, size: 72, color: Color(0xFF1976D2)),
            const SizedBox(height: 16),
            Text('Complete Payment', style: Theme.of(context).textTheme.headlineMedium, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text('Booking ID: $bookingId', style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey), textAlign: TextAlign.center),
            const SizedBox(height: 32),
            _PaymentMethodTile(icon: Icons.credit_card, label: 'Credit / Debit Card'),
            const SizedBox(height: 12),
            _PaymentMethodTile(icon: Icons.account_balance_wallet, label: 'Wallet'),
            const SizedBox(height: 12),
            _PaymentMethodTile(icon: Icons.account_balance, label: 'Bank Transfer'),
            const Spacer(),
            CustomButton(label: 'Pay Now', onPressed: () => context.go(Routes.home)),
          ],
        ),
      ),
    );
  }
}

class _PaymentMethodTile extends StatelessWidget {
  const _PaymentMethodTile({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(icon, color: Theme.of(context).colorScheme.primary),
        title: Text(label),
        trailing: const Icon(Icons.radio_button_unchecked),
      ),
    );
  }
}
