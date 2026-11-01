import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/network/api_errors.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/utils/format.dart';
import '../data/payment_api.dart';
import '../data/razorpay_checkout.dart';

/// Opens the tip sheet for a completed booking; returns the tip paid (rupees), or null if none was.
Future<double?> showTipSheet(
  BuildContext context, {
  required String bookingId,
  required String bookingNumber,
  PaymentApi? paymentApi,
  CheckoutLauncher? checkoutLauncher,
}) =>
    showModalBottomSheet<double>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => TipSheet(
        bookingId: bookingId,
        bookingNumber: bookingNumber,
        paymentApi: paymentApi,
        checkoutLauncher: checkoutLauncher,
      ),
    );

/// A tip for the provider: a few suggested amounts or one of the customer's own, paid online in full to them.
class TipSheet extends StatefulWidget {
  final String bookingId;
  final String bookingNumber;
  final PaymentApi? paymentApi;
  final CheckoutLauncher? checkoutLauncher;

  /// Suggested tips, in rupees, and the range payment_service accepts.
  static const suggested = [20, 50, 100];
  static const minRupees = 10, maxRupees = 2000;

  const TipSheet({super.key, required this.bookingId, required this.bookingNumber, this.paymentApi, this.checkoutLauncher});

  @override
  State<TipSheet> createState() => _TipSheetState();
}

class _TipSheetState extends State<TipSheet> {
  late final PaymentApi _api = widget.paymentApi ?? sl<PaymentApi>();
  late final CheckoutLauncher _checkout = widget.checkoutLauncher ?? RazorpayCheckoutLauncher();
  final _other = TextEditingController();
  // One key per amount, so a retried tap never tips twice but a new amount is a new tip.
  final Map<int, String> _keys = {};
  int? _chosen = TipSheet.suggested[1];
  bool _paying = false;
  String? _error;

  int? get _rupees => _other.text.trim().isEmpty ? _chosen : int.tryParse(_other.text.trim());

  bool get _valid {
    final r = _rupees;
    return r != null && r >= TipSheet.minRupees && r <= TipSheet.maxRupees;
  }

  @override
  void dispose() {
    _other.dispose();
    super.dispose();
  }

  Future<void> _pay() async {
    final rupeesToTip = _rupees;
    if (!_valid || rupeesToTip == null || _paying) return;
    final navigator = Navigator.of(context);
    final l10n = context.l10n;
    setState(() {
      _paying = true;
      _error = null;
    });
    try {
      var result = await _api.tip(
        bookingId: widget.bookingId,
        amountCents: rupeesToTip * 100,
        idempotencyKey: _keys.putIfAbsent(rupeesToTip, PaymentApi.newIdempotencyKey),
      );
      final checkout = result.checkout;
      if (checkout != null) {
        final outcome = await _checkout.open(checkout, description: 'Tip for booking #${widget.bookingNumber}');
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
            return setState(() => _paying = false);
          case CheckoutFailed(:final message):
            return setState(() {
              _paying = false;
              _error = message;
            });
        }
      }
      if (!mounted) return;
      if (result.isCompleted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.tipThanks(rupees(result.amount))), backgroundColor: AppColors.success),
        );
        navigator.pop(result.amount);
      } else {
        setState(() => _paying = false);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _paying = false;
          _error = apiErrorMessage(e);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final r = _rupees;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.tipTitle, style: AppTextStyles.heading3),
          const SizedBox(height: 4),
          Text(l10n.tipBody, style: AppTextStyles.body2.themed(context)),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            children: [
              for (final amount in TipSheet.suggested)
                ChoiceChip(
                  label: Text(rupees(amount.toDouble())),
                  showCheckmark: false,
                  selected: _other.text.trim().isEmpty && _chosen == amount,
                  onSelected: (_) => setState(() {
                    _chosen = amount;
                    _other.clear();
                  }),
                ),
            ],
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _other,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(4)],
            decoration: InputDecoration(
              labelText: l10n.tipOther,
              errorText: _other.text.trim().isNotEmpty && !_valid ? l10n.tipRange : null,
            ),
            onChanged: (_) => setState(() {}),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: AppTextStyles.caption.copyWith(color: context.colors.error)),
          ],
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _valid && !_paying ? _pay : null,
              icon: const Icon(Icons.volunteer_activism_outlined),
              label: Text(l10n.tipPay(rupees((r ?? 0).toDouble()))),
            ),
          ),
        ],
      ),
    );
  }
}
