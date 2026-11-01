import 'package:flutter/material.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/network/api_errors.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/error_widget.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../../payment/data/payment_api.dart';
import '../../payment/data/razorpay_checkout.dart';
import '../data/packages_api.dart';

/// The packages a service is sold in, each with a Buy button; nothing when it has none.
class PackageOffers extends StatefulWidget {
  final String serviceId;
  final double servicePrice;
  final PackagesApi? api;
  final PaymentApi? paymentApi;
  final CheckoutLauncher? checkoutLauncher;

  const PackageOffers({
    super.key,
    required this.serviceId,
    required this.servicePrice,
    this.api,
    this.paymentApi,
    this.checkoutLauncher,
  });

  @override
  State<PackageOffers> createState() => _PackageOffersState();
}

class _PackageOffersState extends State<PackageOffers> {
  late final PackagesApi? _api = widget.api ?? (sl.isRegistered<PackagesApi>() ? sl<PackagesApi>() : null);
  late final PaymentApi? _payments = widget.paymentApi ?? (sl.isRegistered<PaymentApi>() ? sl<PaymentApi>() : null);
  late final CheckoutLauncher _checkout = widget.checkoutLauncher ?? RazorpayCheckoutLauncher();
  // One key per package on this screen, so a retried tap never buys twice.
  final Map<String, String> _keys = {};
  List<PackageOffer> _offers = const [];
  String? _buying;

  @override
  void initState() {
    super.initState();
    _api?.forService(widget.serviceId).then((offers) {
      if (mounted) setState(() => _offers = offers);
    }).catchError((Object _) {});
  }

  Future<void> _buy(PackageOffer offer) async {
    final api = _api, payments = _payments;
    if (api == null || payments == null || _buying != null) return;
    final messenger = ScaffoldMessenger.of(context);
    final l10n = context.l10n;
    setState(() => _buying = offer.id);
    try {
      var result = await api.buy(offer.id, idempotencyKey: _keys.putIfAbsent(offer.id, PaymentApi.newIdempotencyKey));
      final checkout = result.checkout;
      if (checkout != null) {
        final outcome = await _checkout.open(checkout, description: offer.name);
        if (!mounted) return;
        switch (outcome) {
          case CheckoutPaid():
            result = await payments.verify(
              paymentId: result.id,
              orderId: outcome.orderId,
              gatewayPaymentId: outcome.paymentId,
              signature: outcome.signature,
            );
          case CheckoutCancelled():
            return;
          case CheckoutFailed(:final message):
            messenger.showSnackBar(SnackBar(content: Text(message), backgroundColor: AppColors.error));
            return;
        }
      }
      if (result.isCompleted) {
        messenger.showSnackBar(SnackBar(content: Text(l10n.packageBought(offer.name)), backgroundColor: AppColors.success));
      }
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    } finally {
      if (mounted) setState(() => _buying = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_offers.isEmpty) return const SizedBox.shrink();
    final l10n = context.l10n;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 24),
        Semantics(header: true, child: Text(l10n.packagesTitle, style: AppTextStyles.subtitle1)),
        const SizedBox(height: 8),
        for (final offer in _offers)
          Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: Icon(Icons.local_offer_outlined, color: context.colors.primary),
              title: Text(offer.name),
              subtitle: Text([
                l10n.packageTerms(offer.visits, offer.validDays),
                if (offer.savingOn(widget.servicePrice) > 0) l10n.packageSaving(rupees(offer.savingOn(widget.servicePrice))),
              ].join(' · ')),
              trailing: FilledButton(
                onPressed: _buying == null ? () => _buy(offer) : null,
                child: Text(l10n.packageBuy(rupees(offer.price))),
              ),
            ),
          ),
      ],
    );
  }
}

/// The customer's packages: visits left and until when.
class MyPackagesPage extends StatefulWidget {
  final PackagesApi? api;

  const MyPackagesPage({super.key, this.api});

  @override
  State<MyPackagesPage> createState() => _MyPackagesPageState();
}

class _MyPackagesPageState extends State<MyPackagesPage> {
  late final PackagesApi _api = widget.api ?? sl<PackagesApi>();
  List<OwnedPackage>? _packages;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final packages = await _api.mine();
      if (mounted) setState(() => _packages = packages);
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final packages = _packages;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.myPackages)),
      body: packages == null
          ? (_error != null ? AppErrorWidget(message: _error!, onRetry: _load) : const LoadingIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: packages.isEmpty
                  ? ListView(
                      padding: const EdgeInsets.all(32),
                      children: [Text(l10n.noPackages, textAlign: TextAlign.center, style: AppTextStyles.body2.themed(context))],
                    )
                  : ListView.separated(
                      itemCount: packages.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, i) {
                        final p = packages[i];
                        return ListTile(
                          leading: Icon(Icons.local_offer, color: p.usable ? context.colors.primary : context.palette.muted),
                          title: Text(p.name),
                          subtitle: Text(p.usable
                              ? [
                                  l10n.packageVisitsLeft(p.visitsLeft, p.visitsTotal),
                                  if (p.expiresAt != null) l10n.packageValidUntil(dayAndMonth(p.expiresAt!, l10n)),
                                ].join(' · ')
                              : p.status == 'REFUNDED'
                                  ? l10n.packageRefunded
                                  : l10n.packageUsedUp),
                        );
                      },
                    ),
            ),
    );
  }
}
