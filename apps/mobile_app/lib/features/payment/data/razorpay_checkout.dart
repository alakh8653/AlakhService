import 'dart:async';

import 'package:razorpay_flutter/razorpay_flutter.dart';

import 'payment_api.dart';

/// How a checkout ended.
sealed class CheckoutOutcome {
  const CheckoutOutcome();
}

/// Razorpay took the payment; the server must still verify [signature].
class CheckoutPaid extends CheckoutOutcome {
  final String orderId;
  final String paymentId;
  final String signature;

  const CheckoutPaid({required this.orderId, required this.paymentId, required this.signature});
}

class CheckoutCancelled extends CheckoutOutcome {
  const CheckoutCancelled();
}

class CheckoutFailed extends CheckoutOutcome {
  final String message;

  const CheckoutFailed(this.message);
}

/// Opens the gateway's payment sheet for a server-created order.
abstract class CheckoutLauncher {
  Future<CheckoutOutcome> open(GatewayCheckout checkout, {required String description, String? contact, String? email});
}

/// Razorpay's native checkout (Android and iOS).
class RazorpayCheckoutLauncher implements CheckoutLauncher {
  @override
  Future<CheckoutOutcome> open(GatewayCheckout checkout, {required String description, String? contact, String? email}) {
    final razorpay = Razorpay();
    final done = Completer<CheckoutOutcome>();
    void finish(CheckoutOutcome outcome) {
      if (!done.isCompleted) done.complete(outcome);
      razorpay.clear();
    }

    razorpay.on(Razorpay.EVENT_PAYMENT_SUCCESS, (PaymentSuccessResponse r) {
      finish(CheckoutPaid(
        orderId: r.orderId ?? checkout.orderId,
        paymentId: r.paymentId ?? '',
        signature: r.signature ?? '',
      ));
    });
    razorpay.on(Razorpay.EVENT_PAYMENT_ERROR, (PaymentFailureResponse r) {
      finish(r.code == Razorpay.PAYMENT_CANCELLED
          ? const CheckoutCancelled()
          : CheckoutFailed(r.message ?? 'The payment did not go through.'));
    });
    // Wallets that complete outside the sheet are confirmed later by the server's webhook.
    razorpay.on(Razorpay.EVENT_EXTERNAL_WALLET, (ExternalWalletResponse _) {
      finish(const CheckoutFailed('Finish the payment in your wallet app; it will show here once confirmed.'));
    });

    razorpay.open({
      'key': checkout.keyId,
      'order_id': checkout.orderId,
      'amount': checkout.amountCents,
      'currency': checkout.currency,
      'name': 'AlakhService',
      'description': description,
      'prefill': {if (contact != null) 'contact': contact, if (email != null) 'email': email},
    });
    return done.future;
  }
}
