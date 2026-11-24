import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../app/app_links.dart';
import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../../reviews/data/reviews_api.dart';
import '../../reviews/presentation/reviews_widgets.dart';
import '../data/shop_owner_api.dart';

String _day(DateTime day) => DateFormat('EEE, d MMM yyyy').format(day);

String _isoDay(DateTime day) =>
    '${day.year.toString().padLeft(4, '0')}-${day.month.toString().padLeft(2, '0')}-${day.day.toString().padLeft(2, '0')}';

/// Days the business is shut, in a tap: today, tomorrow or any date. Bookings already made stay, so the owner
/// is told to look after them.
class OwnerDaysOffPage extends StatefulWidget {
  final String shopId;
  final ShopOwnerApi? api;
  final DateTime Function() now;

  const OwnerDaysOffPage({super.key, required this.shopId, this.api, this.now = DateTime.now});

  @override
  State<OwnerDaysOffPage> createState() => _OwnerDaysOffPageState();
}

class _OwnerDaysOffPageState extends State<OwnerDaysOffPage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  List<DateTime>? _days;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final days = await _api.daysOff(widget.shopId);
      if (mounted) setState(() => _days = days);
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _run(Future<void> Function() change) async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await change();
      await _load();
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _pick() async {
    final today = widget.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: today,
      firstDate: today,
      lastDate: today.add(const Duration(days: 364)),
    );
    if (picked != null) await _run(() => _api.addDayOff(widget.shopId, _isoDay(picked)));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final days = _days;
    final today = widget.now();
    return Scaffold(
      appBar: AppBar(title: Text(l10n.ownerDaysOff)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.ownerDaysOffHelp, style: AppTextStyles.body2.themed(context)),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton(
                  onPressed: _saving ? null : () => _run(() => _api.addDayOff(widget.shopId, _isoDay(today))),
                  child: Text(l10n.ownerOffToday),
                ),
                OutlinedButton(
                  onPressed: _saving
                      ? null
                      : () => _run(() => _api.addDayOff(widget.shopId, _isoDay(today.add(const Duration(days: 1))))),
                  child: Text(l10n.ownerOffTomorrow),
                ),
                OutlinedButton(onPressed: _saving ? null : _pick, child: Text(l10n.ownerOffPick)),
              ],
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: AppTextStyles.body2.copyWith(color: AppColors.error)),
            ],
            const SizedBox(height: 16),
            if (days == null && _error == null)
              const LoadingIndicator()
            else if (days != null && days.isEmpty)
              Text(l10n.ownerNoDaysOff, style: AppTextStyles.body2.themed(context))
            else
              for (final day in days ?? const <DateTime>[])
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.event_busy_outlined),
                  title: Text(_day(day), style: AppTextStyles.body1),
                  trailing: TextButton(
                    onPressed: _saving ? null : () => _run(() => _api.removeDayOff(widget.shopId, _isoDay(day))),
                    child: Text(l10n.reportRemoveEntry),
                  ),
                ),
          ],
        ),
      ),
    );
  }
}

/// What customers said, with the owner's public reply under each.
class OwnerReviewsPage extends StatefulWidget {
  final String shopId;
  final ShopOwnerApi? api;
  final ReviewsApi? reviews;

  const OwnerReviewsPage({super.key, required this.shopId, this.api, this.reviews});

  @override
  State<OwnerReviewsPage> createState() => _OwnerReviewsPageState();
}

class _OwnerReviewsPageState extends State<OwnerReviewsPage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  late final ReviewsApi _reviews = widget.reviews ?? sl<ReviewsApi>();
  List<Review>? _items;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final page = await _reviews.reviews(widget.shopId, limit: 50);
      if (mounted) setState(() => _items = page.items);
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _reply(Review review) async {
    final messenger = ScaffoldMessenger.of(context);
    final text = await showDialog<String>(
      context: context,
      builder: (_) => _ReplyDialog(initial: review.reply?.text ?? ''),
    );
    if (text == null || text.isEmpty) return;
    try {
      await _api.replyToReview(widget.shopId, review.id, text);
      await _load();
    } on ServerException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final items = _items;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.ownerReviews)),
      body: _error != null
          ? Center(child: Text(_error!))
          : items == null
              ? const LoadingIndicator()
              : items.isEmpty
                  ? Center(child: Text(l10n.ownerNoReviews))
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        for (final review in items) ...[
                          ReviewTile(review: review),
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton(
                              onPressed: () => _reply(review),
                              child: Text(review.reply == null ? l10n.ownerReply : l10n.ownerEditReply),
                            ),
                          ),
                          const Divider(),
                        ],
                      ],
                    ),
    );
  }
}

/// Keeps its own text controller, which has to outlive the dialog's closing animation.
class _ReplyDialog extends StatefulWidget {
  final String initial;

  const _ReplyDialog({required this.initial});

  @override
  State<_ReplyDialog> createState() => _ReplyDialogState();
}

class _ReplyDialogState extends State<_ReplyDialog> {
  late final _text = TextEditingController(text: widget.initial);

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return AlertDialog(
      title: Text(l10n.ownerReply),
      content: TextField(
        controller: _text,
        autofocus: true,
        maxLines: 3,
        maxLength: 500,
        decoration: InputDecoration(helperText: l10n.ownerReplyHelp),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(l10n.notNow)),
        FilledButton(onPressed: () => Navigator.pop(context, _text.text.trim()), child: Text(l10n.save)),
      ],
    );
  }
}

/// Who keeps coming back. Names only: contact stays on the platform, so there is no number to show.
class OwnerCustomersPage extends StatefulWidget {
  final String shopId;
  final ShopOwnerApi? api;

  const OwnerCustomersPage({super.key, required this.shopId, this.api});

  @override
  State<OwnerCustomersPage> createState() => _OwnerCustomersPageState();
}

class _OwnerCustomersPageState extends State<OwnerCustomersPage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  List<ShopCustomer>? _items;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final items = await _api.customers(widget.shopId);
      if (mounted) setState(() => _items = items);
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final items = _items;
    final rupees = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.ownerCustomers)),
      body: _error != null
          ? Center(child: Text(_error!))
          : items == null
              ? const LoadingIndicator()
              : items.isEmpty
                  ? Center(child: Text(l10n.ownerNoCustomers))
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        Text(
                          l10n.ownerCustomersSummary(items.length, items.where((c) => c.visits > 1).length),
                          style: AppTextStyles.body2.themed(context),
                        ),
                        for (final customer in items)
                          ListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text(customer.name, style: AppTextStyles.body1),
                            subtitle: Text(l10n.ownerCustomerLine(customer.visits, _day(customer.lastVisit))),
                            trailing: Text(rupees.format(customer.spent)),
                          ),
                      ],
                    ),
    );
  }
}

/// The message and link an owner sends to their customers, on WhatsApp or anywhere else.
class OwnerSharePage extends StatelessWidget {
  final OwnerShop shop;
  final Future<bool> Function(Uri)? open;

  const OwnerSharePage({super.key, required this.shop, this.open});

  String get _link => 'https://$appLinkDomain/s/${shop.id}';

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final message = l10n.ownerShareMessage(shop.name, _link);
    Future<void> whatsApp() async {
      final messenger = ScaffoldMessenger.of(context);
      final uri = Uri.https('wa.me', '/', {'text': message});
      final opened = open != null ? await open!(uri) : await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!opened) messenger.showSnackBar(SnackBar(content: Text(l10n.ownerShareFailed)));
    }

    Future<void> copy() async {
      final messenger = ScaffoldMessenger.of(context);
      await Clipboard.setData(ClipboardData(text: message));
      messenger.showSnackBar(SnackBar(content: Text(l10n.ownerShareCopied)));
    }

    return Scaffold(
      appBar: AppBar(title: Text(l10n.ownerShare)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (!shop.approved)
              Text(l10n.ownerShareNotYet, style: AppTextStyles.body1)
            else ...[
              Text(l10n.ownerShareHelp, style: AppTextStyles.body2.themed(context)),
              const SizedBox(height: 12),
              Card(child: Padding(padding: const EdgeInsets.all(16), child: SelectableText(message))),
              const SizedBox(height: 12),
              FilledButton.icon(
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                icon: const Icon(Icons.chat_outlined),
                label: Text(l10n.ownerShareWhatsApp),
                onPressed: whatsApp,
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                icon: const Icon(Icons.copy),
                label: Text(l10n.ownerShareCopy),
                onPressed: copy,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
