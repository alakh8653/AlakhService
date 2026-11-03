import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../data/shop_owner_api.dart';

String _money(num amount) => NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: amount == amount.roundToDouble() ? 0 : 2,
    ).format(amount);

String _periodLabel(String period, AppLocalizations l) => switch (period) {
      'daily' => l.reportDaily,
      'weekly' => l.reportWeekly,
      'yearly' => l.reportYearly,
      _ => l.reportMonthly,
    };

String _categoryLabel(String category, AppLocalizations l) => switch (category) {
      'MATERIALS' => l.entryMaterials,
      'SPARE_PARTS' => l.entrySpareParts,
      'TRAVEL' => l.entryTravel,
      'RENT' => l.entryRent,
      'STAFF' => l.entryStaff,
      'TOOLS' => l.entryTools,
      'BILLS' => l.entryBills,
      'MARKETING' => l.entryMarketing,
      'OUTSIDE_WORK' => l.entryOutsideWork,
      _ => l.entryOther,
    };

/// What the business made for a day, week, month or year: what came in, what went out and the profit, with
/// expenses and outside income added in a couple of taps.
class OwnerReportsPage extends StatefulWidget {
  final String shopId;
  final ShopOwnerApi? api;

  const OwnerReportsPage({super.key, required this.shopId, this.api});

  @override
  State<OwnerReportsPage> createState() => _OwnerReportsPageState();
}

class _OwnerReportsPageState extends State<OwnerReportsPage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  String _period = 'monthly';
  ShopReport? _report;
  List<CashEntry> _entries = const [];
  bool _sending = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _report = null;
      _error = null;
    });
    final period = _period;
    try {
      final report = await _api.report(widget.shopId, period);
      final entries = await _api.cashEntries(widget.shopId, report.from, report.to);
      if (mounted && period == _period) {
        setState(() {
          _report = report;
          _entries = entries;
        });
      }
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _add(String kind) async {
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _EntrySheet(kind: kind, shopId: widget.shopId, api: _api),
    );
    if (added == true) await _load();
  }

  Future<void> _remove(CashEntry entry) async {
    try {
      await _api.deleteCashEntry(widget.shopId, entry.id);
      await _load();
    } on ServerException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _sendNow() async {
    final l10n = context.l10n;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _sending = true);
    try {
      final sentTo = await _api.sendReport(widget.shopId, _period);
      final outside = sentTo.where((c) => c != 'app').toList();
      messenger.showSnackBar(SnackBar(
        content: Text(outside.isEmpty ? l10n.reportSentAppOnly : l10n.reportSentTo(outside.join(', '))),
      ));
    } on ServerException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Widget _row(String label, num amount, {bool strong = false, Color? color}) {
    final style = (strong ? AppTextStyles.heading3 : AppTextStyles.body1).copyWith(color: color);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(label, style: strong ? style : AppTextStyles.body2.themed(context))),
          Text(_money(amount), style: style),
        ],
      ),
    );
  }

  Widget _summary(ShopReport r, AppLocalizations l10n) {
    final loss = r.profit < 0;
    final change = r.profitChangePercent;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(r.label, style: AppTextStyles.caption.themed(context)),
            const SizedBox(height: 8),
            _row(
              loss ? l10n.reportLoss : l10n.reportProfit,
              r.profit,
              strong: true,
              color: loss ? AppColors.error : AppColors.success,
            ),
            if (change != null)
              Text(
                change >= 0 ? l10n.reportUp(change.abs().toString()) : l10n.reportDown(change.abs().toString()),
                style: AppTextStyles.caption.themed(context),
              ),
            const Divider(height: 24),
            Text(l10n.reportBookingsDone(r.bookings), style: AppTextStyles.body2.themed(context)),
            const SizedBox(height: 4),
            _row(l10n.reportCustomersPaid, r.gross),
            _row(l10n.reportCash, r.cash),
            _row(l10n.reportOnline, r.online),
            _row(l10n.reportCommission, 0 - (r.commission + r.gst)),
            _row(l10n.reportEarned, r.earned),
            _row(l10n.reportOtherIncome, r.otherIncome),
            _row(l10n.reportExpenses, 0 - r.expenses),
            if (r.tips != 0) _row(l10n.reportTips, r.tips),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final report = _report;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.ownerReports),
        actions: [
          IconButton(
            key: const ValueKey('report-settings'),
            icon: const Icon(Icons.settings_outlined),
            tooltip: l10n.reportSettingsTitle,
            onPressed: () => Navigator.push<void>(
              context,
              MaterialPageRoute(builder: (_) => OwnerReportSettingsPage(shopId: widget.shopId, api: _api)),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Wrap(
              spacing: 8,
              children: [
                for (final period in const ['daily', 'weekly', 'monthly', 'yearly'])
                  ChoiceChip(
                    label: Text(_periodLabel(period, l10n)),
                    selected: _period == period,
                    onSelected: (_) {
                      setState(() => _period = period);
                      _load();
                    },
                  ),
              ],
            ),
            const SizedBox(height: 12),
            if (_error != null) ...[
              Text(_error!, style: AppTextStyles.body2.copyWith(color: AppColors.error)),
              TextButton(onPressed: _load, child: Text(l10n.retry)),
            ] else if (report == null)
              const Padding(padding: EdgeInsets.all(32), child: LoadingIndicator())
            else ...[
              _summary(report, l10n),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.remove_circle_outline),
                      label: Text(l10n.reportAddExpense),
                      onPressed: () => _add('EXPENSE'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.add_circle_outline),
                      label: Text(l10n.reportAddIncome),
                      onPressed: () => _add('INCOME'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(l10n.reportRecordedOnly, style: AppTextStyles.caption.themed(context)),
              if (report.breakdown.isNotEmpty) ...[
                const SizedBox(height: 16),
                Text(l10n.reportBreakdown, style: AppTextStyles.heading3),
                for (final line in report.breakdown)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    title: Text(line.label, style: AppTextStyles.body2.themed(context)),
                    trailing: Text(_money(line.profit), style: AppTextStyles.body1),
                  ),
              ],
              if (_entries.isNotEmpty) ...[
                const SizedBox(height: 16),
                Text(l10n.reportEntries, style: AppTextStyles.heading3),
                for (final entry in _entries)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    title: Text(_categoryLabel(entry.category, l10n), style: AppTextStyles.body2.themed(context)),
                    subtitle: Text([entry.onDate, if (entry.note != null) entry.note!].join(' · ')),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(_money(entry.kind == 'EXPENSE' ? -entry.amount : entry.amount)),
                        IconButton(
                          icon: const Icon(Icons.delete_outline),
                          tooltip: l10n.reportRemoveEntry,
                          onPressed: () => _remove(entry),
                        ),
                      ],
                    ),
                  ),
              ],
              const SizedBox(height: 16),
              FilledButton.icon(
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                icon: const Icon(Icons.send_outlined),
                label: Text(l10n.reportSendNow),
                onPressed: _sending ? null : _sendNow,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// An expense or outside income: pick what it was, type the amount.
class _EntrySheet extends StatefulWidget {
  final String kind;
  final String shopId;
  final ShopOwnerApi api;

  const _EntrySheet({required this.kind, required this.shopId, required this.api});

  @override
  State<_EntrySheet> createState() => _EntrySheetState();
}

class _EntrySheetState extends State<_EntrySheet> {
  final _amount = TextEditingController();
  final _note = TextEditingController();
  late String _category = _expense ? 'MATERIALS' : 'OUTSIDE_WORK';
  bool _saving = false;
  String? _error;

  bool get _expense => widget.kind == 'EXPENSE';

  @override
  void dispose() {
    _amount.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final l10n = context.l10n;
    final amount = double.tryParse(_amount.text.trim());
    if (amount == null || amount <= 0) {
      setState(() => _error = l10n.ownerEnterNumber);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.addCashEntry(widget.shopId, widget.kind, _category, amount, note: _note.text.trim());
      if (mounted) Navigator.pop(context, true);
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final categories = _expense
        ? const ['MATERIALS', 'SPARE_PARTS', 'TRAVEL', 'RENT', 'STAFF', 'TOOLS', 'BILLS', 'MARKETING', 'OTHER']
        : const ['OUTSIDE_WORK', 'OTHER'];
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_expense ? l10n.reportAddExpense : l10n.reportAddIncome, style: AppTextStyles.heading3),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                for (final category in categories)
                  ChoiceChip(
                    label: Text(_categoryLabel(category, l10n)),
                    selected: _category == category,
                    onSelected: (_) => setState(() => _category = category),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              key: const ValueKey('entry-amount'),
              controller: _amount,
              autofocus: true,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
              decoration: InputDecoration(labelText: l10n.reportAmount, prefixText: '₹ '),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _note,
              maxLength: 200,
              decoration: InputDecoration(labelText: l10n.reportNote),
            ),
            if (_error != null) Text(_error!, style: AppTextStyles.body2.copyWith(color: AppColors.error)),
            const SizedBox(height: 8),
            FilledButton(
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
              onPressed: _saving ? null : _save,
              child: Text(l10n.save),
            ),
          ],
        ),
      ),
    );
  }
}

/// Which reports reach the owner, and where. WhatsApp stays off until they say yes here.
class OwnerReportSettingsPage extends StatefulWidget {
  final String shopId;
  final ShopOwnerApi? api;

  const OwnerReportSettingsPage({super.key, required this.shopId, this.api});

  @override
  State<OwnerReportSettingsPage> createState() => _OwnerReportSettingsPageState();
}

class _OwnerReportSettingsPageState extends State<OwnerReportSettingsPage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  ReportSettings? _settings;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final settings = await _api.reportSettings(widget.shopId);
      if (mounted) setState(() => _settings = settings);
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _change(ReportSettings next) async {
    final before = _settings;
    setState(() {
      _settings = next;
      _error = null;
    });
    try {
      await _api.saveReportSettings(widget.shopId, next);
    } on ServerException catch (e) {
      if (mounted) {
        setState(() {
          _settings = before;
          _error = e.message;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final s = _settings;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.reportSettingsTitle)),
      body: s == null
          ? (_error == null ? const LoadingIndicator() : Center(child: Text(_error!)))
          : ListView(
              padding: const EdgeInsets.all(8),
              children: [
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(8),
                    child: Text(_error!, style: AppTextStyles.body2.copyWith(color: AppColors.error)),
                  ),
                ListTile(title: Text(l10n.reportWhich, style: AppTextStyles.heading3)),
                SwitchListTile(
                  title: Text(l10n.reportDaily),
                  value: s.daily,
                  onChanged: (v) => _change(s.copyWith(daily: v)),
                ),
                SwitchListTile(
                  title: Text(l10n.reportWeekly),
                  value: s.weekly,
                  onChanged: (v) => _change(s.copyWith(weekly: v)),
                ),
                SwitchListTile(
                  title: Text(l10n.reportMonthly),
                  value: s.monthly,
                  onChanged: (v) => _change(s.copyWith(monthly: v)),
                ),
                SwitchListTile(
                  title: Text(l10n.reportYearly),
                  subtitle: Text(l10n.reportYearlyHelp),
                  value: s.yearly,
                  onChanged: (v) => _change(s.copyWith(yearly: v)),
                ),
                ListTile(title: Text(l10n.reportWhere, style: AppTextStyles.heading3)),
                SwitchListTile(
                  title: Text(l10n.reportEmail),
                  value: s.email,
                  onChanged: (v) => _change(s.copyWith(email: v)),
                ),
                SwitchListTile(
                  key: const ValueKey('report-whatsapp'),
                  title: Text(l10n.reportWhatsApp),
                  subtitle: Text(l10n.reportWhatsAppConsent),
                  value: s.whatsapp,
                  onChanged: (v) => _change(s.copyWith(whatsapp: v)),
                ),
              ],
            ),
    );
  }
}
