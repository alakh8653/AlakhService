import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../data/payment_api.dart';

/// Shows an invoice page's HTML. Swapped out in tests, where there is no platform web view.
typedef HtmlViewBuilder = Widget Function(BuildContext context, String html);

/// A payment's invoice (payment_service), fetched with the customer's session so it never needs a
/// token in a link, and shown in a plain web view with scripts off.
class InvoicePage extends StatefulWidget {
  final String paymentId;
  final PaymentApi? paymentApi;
  final HtmlViewBuilder? viewer;

  const InvoicePage({super.key, required this.paymentId, this.paymentApi, this.viewer});

  @override
  State<InvoicePage> createState() => _InvoicePageState();
}

class _InvoicePageState extends State<InvoicePage> {
  String? _html;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final html = await (widget.paymentApi ?? sl<PaymentApi>()).invoiceHtml(widget.paymentId);
      if (mounted) setState(() => _html = html);
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final html = _html;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.invoiceTitle)),
      body: _error != null
          ? AppErrorWidget(message: _error!, onRetry: _load)
          : html == null
              ? LoadingIndicator(message: l10n.invoiceLoading)
              : (widget.viewer ?? _webView)(context, html),
    );
  }

  static Widget _webView(BuildContext context, String html) => WebViewWidget(
        controller: WebViewController()
          ..setJavaScriptMode(JavaScriptMode.disabled)
          ..loadHtmlString(html),
      );
}
