import 'package:flutter/material.dart';

import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/utils/format.dart';
import '../../domain/entities/booking.dart';

/// What the customer is told about a booking's payment.
enum PaymentShown { paid, refunded, partlyRefunded, cash }

/// The booking's payment_status when the server sends it, else what the payments list says
/// ([fromPayments] is 'paid', 'cash' or null, see PaymentApi.paymentStateByBooking).
PaymentShown? paymentShown(Booking booking, String? fromPayments) {
  switch (booking.paymentStatus) {
    case PaymentStatus.paid:
      return PaymentShown.paid;
    case PaymentStatus.refunded:
      return PaymentShown.refunded;
    case PaymentStatus.partiallyRefunded:
      return PaymentShown.partlyRefunded;
    case PaymentStatus.unpaid:
      // Not paid yet; the customer may have chosen to pay in person.
      return fromPayments == 'cash' ? PaymentShown.cash : null;
  }
  return switch (fromPayments) {
    'paid' => PaymentShown.paid,
    'cash' => PaymentShown.cash,
    _ => null,
  };
}

/// Whether to offer the Pay button: payable, and not already paid by either account.
bool canStillPay(Booking booking, String? fromPayments) =>
    booking.canPay && !booking.isPaid && fromPayments != 'paid';

String paymentShownLabel(AppLocalizations l10n, PaymentShown shown) => switch (shown) {
      PaymentShown.paid => l10n.paid,
      PaymentShown.refunded => l10n.statusRefunded,
      PaymentShown.partlyRefunded => l10n.paymentPartlyRefunded,
      PaymentShown.cash => l10n.payingCash,
    };

Color paymentShownColor(BuildContext context, PaymentShown shown) => switch (shown) {
      PaymentShown.paid => context.palette.success,
      PaymentShown.cash => context.palette.warning,
      PaymentShown.refunded || PaymentShown.partlyRefunded => context.palette.info,
    };

/// Asks before cancelling, with the refund policy: free until two hours before, a fee may apply after.
Future<bool> confirmCancelBooking(BuildContext context, Booking booking, {DateTime? now}) async {
  final l10n = context.l10n;
  final late = booking.inCancellationFeeWindow(now ?? DateTime.now());
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: Text(l10n.cancelBookingQuestion),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.cancelBookingBody(booking.serviceName, friendlyDateTime(booking.scheduledAt, l10n: l10n))),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline, size: 16, color: late ? context.palette.warning : context.palette.muted),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  late ? l10n.cancelPolicyLate : l10n.cancelPolicy,
                  style: AppTextStyles.caption.copyWith(color: late ? context.palette.warning : context.palette.muted),
                ),
              ),
            ],
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(l10n.keepBooking)),
        TextButton(
          onPressed: () => Navigator.pop(dialogContext, true),
          style: TextButton.styleFrom(foregroundColor: context.colors.error),
          child: Text(l10n.yesCancel),
        ),
      ],
    ),
  );
  return confirmed == true;
}
