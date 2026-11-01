import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/network/api_errors.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/utils/format.dart';
import '../data/shop_line_api.dart';

/// The owner runs today's line from the phone: who on the team is free, serving or on a break, everyone
/// waiting in order with their expected time, and the next customer, walk-ins, check-ins and no-shows.
/// For any kind of shop (salon, clinic, repair counter): the team's services decide who takes whom.
class ShopLinePage extends StatefulWidget {
  final OwnedShop shop;
  final ShopLineApi? api;
  final Duration refreshEvery;

  const ShopLinePage({super.key, required this.shop, this.api, this.refreshEvery = const Duration(seconds: 30)});

  @override
  State<ShopLinePage> createState() => _ShopLinePageState();
}

class _ShopLinePageState extends State<ShopLinePage> {
  late final ShopLineApi _api = widget.api ?? sl<ShopLineApi>();
  List<LineEntry>? _line;
  List<TeamMember> _team = const [];
  String? _error;
  bool _busy = false;
  Timer? _timer;

  String get _shopId => widget.shop.id;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(widget.refreshEvery, (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final results = await Future.wait([_api.line(_shopId), _api.team(_shopId)]);
      if (!mounted) return;
      setState(() {
        _line = results[0] as List<LineEntry>;
        _team = results[1] as List<TeamMember>;
        _error = null;
      });
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  Future<void> _run(Future<void> Function() action, [String? done]) async {
    if (_busy) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      await action();
      if (done != null) messenger.showSnackBar(SnackBar(content: Text(done)));
      await _load();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _addWalkIn() async {
    final l10n = context.l10n;
    final services = widget.shop.services;
    var serviceId = services.keys.isEmpty ? null : services.keys.first;
    final name = TextEditingController();
    final added = await showModalBottomSheet<(String, String)>(
      context: context,
      isScrollControlled: true,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, setSheet) => Padding(
          padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + MediaQuery.of(sheet).viewInsets.bottom),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(l10n.shopLineAddWalkIn, style: AppTextStyles.heading3),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: serviceId,
                decoration: InputDecoration(labelText: l10n.shopLineService),
                items: [for (final e in services.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
                onChanged: (v) => setSheet(() => serviceId = v),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: name,
                maxLength: 80,
                decoration: InputDecoration(labelText: l10n.shopLineWalkInName),
              ),
              FilledButton(
                onPressed: () {
                  if (serviceId != null && name.text.trim().isNotEmpty) Navigator.pop(sheet, (serviceId!, name.text.trim()));
                },
                child: Text(l10n.shopLineAdd),
              ),
            ],
          ),
        ),
      ),
    );
    if (added == null || !mounted) return;
    await _run(() async {
      final entry = await _api.addWalkIn(_shopId, added.$1, added.$2);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l10n.shopLineAdded(entry.name, entry.position ?? 1))));
      }
    });
  }

  String _status(TeamMember m) {
    final l10n = context.l10n;
    return switch (m.status) {
      'BREAK' => m.until == null ? l10n.shopLineBreak : l10n.shopLineOnBreak(clockTime(m.until!)),
      'OFF' => l10n.shopLineOffToday,
      _ => m.servingName != null ? l10n.shopLineServing(m.servingName!) : l10n.shopLineFree,
    };
  }

  Widget _member(TeamMember m) {
    final l10n = context.l10n;
    return Card(
      key: ValueKey('team-${m.staffId}'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(m.name, style: AppTextStyles.subtitle1),
            Text(_status(m), style: AppTextStyles.body2.themed(context)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                if (m.servingBookingId != null)
                  FilledButton(onPressed: _busy ? null : () => _run(() => _api.finish(m.servingBookingId!)), child: Text(l10n.shopLineDone))
                else if (m.status == 'AVAILABLE')
                  FilledButton(
                    onPressed: _busy ? null : () => _run(() => _api.callNext(_shopId, staffId: m.staffId)),
                    child: Text(l10n.shopLineNext),
                  ),
                if (m.status == 'AVAILABLE') ...[
                  OutlinedButton(
                    onPressed: _busy ? null : () => _run(() => _api.setStatus(_shopId, m.staffId, 'BREAK', minutes: 15)),
                    child: Text(l10n.shopLineBreak),
                  ),
                  OutlinedButton(
                    onPressed: _busy ? null : () => _run(() => _api.setStatus(_shopId, m.staffId, 'OFF')),
                    child: Text(l10n.shopLineOff),
                  ),
                ] else
                  OutlinedButton(
                    onPressed: _busy ? null : () => _run(() => _api.setStatus(_shopId, m.staffId, 'AVAILABLE')),
                    child: Text(l10n.shopLineBack),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _entry(LineEntry e) {
    final l10n = context.l10n;
    final details = [
      if (e.serviceId != null && widget.shop.services[e.serviceId] != null) widget.shop.services[e.serviceId]!,
      if (e.staffName != null) e.staffName!,
      if (e.state == 'IN_PROGRESS' && e.estimatedEnd != null) '→ ${clockTime(e.estimatedEnd!)}',
      if (e.waiting && e.estimatedStart != null) clockTime(e.estimatedStart!),
      if (e.waiting && e.runningLateMinutes > 0) l10n.shopLineLate(e.runningLateMinutes),
    ];
    final actions = <(String, Future<void> Function())>[
      if (e.waiting) (l10n.shopLineStart, () => _api.start(e.bookingId)),
      if ((e.waiting || e.state == 'CHECK_IN_NEEDED') && !e.checkedIn) (l10n.shopLineCheckIn, () => _api.checkIn(e.bookingId)),
      if (e.canMarkNoShow) (l10n.shopLineNoShow, () => _api.noShow(e.bookingId)),
      if (e.state == 'IN_PROGRESS') (l10n.shopLineDone, () => _api.finish(e.bookingId)),
    ];
    return ListTile(
      key: ValueKey('line-${e.bookingId}'),
      leading: CircleAvatar(
        backgroundColor: context.colors.primaryContainer,
        child: Text(e.state == 'IN_PROGRESS' ? l10n.shopLineNow : '#${e.position ?? '–'}', style: AppTextStyles.caption),
      ),
      title: Text([e.name, if (e.vip) 'VIP', if (e.walkIn) l10n.shopLineWalkIn].join(' · ')),
      subtitle: Text(details.join(' · ')),
      trailing: actions.isEmpty
          ? null
          : PopupMenuButton<int>(
              enabled: !_busy,
              onSelected: (i) => _run(actions[i].$2),
              itemBuilder: (_) => [for (var i = 0; i < actions.length; i++) PopupMenuItem(value: i, child: Text(actions[i].$1))],
            ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final line = _line;
    final waiting = line?.where((e) => e.waiting).length ?? 0;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.shopLineTitle)),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _busy || widget.shop.services.isEmpty ? null : _addWalkIn,
        icon: const Icon(Icons.person_add_alt_1),
        label: Text(l10n.shopLineAddWalkIn),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
          children: [
            Text(widget.shop.name, style: AppTextStyles.subtitle1),
            Text(l10n.shopLineWaiting(waiting), style: AppTextStyles.body2.themed(context)),
            const SizedBox(height: 12),
            if (_team.isNotEmpty) ...[
              Text(l10n.shopLineTeam, style: AppTextStyles.subtitle2),
              for (final m in _team) _member(m),
              const SizedBox(height: 12),
            ] else if (waiting > 0)
              FilledButton(onPressed: _busy ? null : () => _run(() => _api.callNext(_shopId)), child: Text(l10n.shopLineNext)),
            if (_error != null) Text(_error!, style: AppTextStyles.body2.copyWith(color: context.colors.error)),
            if (line == null && _error == null) const Center(child: CircularProgressIndicator()),
            if (line != null && line.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 48),
                child: Text(l10n.shopLineEmpty, textAlign: TextAlign.center, style: AppTextStyles.subtitle1),
              ),
            if (line != null) for (final e in line) _entry(e),
          ],
        ),
      ),
    );
  }
}
