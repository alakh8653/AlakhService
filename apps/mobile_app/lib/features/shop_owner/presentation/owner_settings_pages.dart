import 'package:flutter/material.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/custom_button.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../data/shop_owner_api.dart';
import 'shop_setup_page.dart';
import 'week_hours_editor.dart';

/// What the business offers: add a service, or switch one off for now.
class OwnerServicesPage extends StatefulWidget {
  final String shopId;
  final ShopOwnerApi? api;

  const OwnerServicesPage({super.key, required this.shopId, this.api});

  @override
  State<OwnerServicesPage> createState() => _OwnerServicesPageState();
}

class _OwnerServicesPageState extends State<OwnerServicesPage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  List<OwnerService>? _services;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final services = await _api.services(widget.shopId);
      if (mounted) {
        setState(() {
          _services = services;
          _error = null;
        });
      }
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _setActive(OwnerService service, bool active) async {
    try {
      await _api.setServiceActive(service.id, active);
      await _load();
    } on ServerException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _add() async {
    final added = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => _AddServicePage(
          shopId: widget.shopId,
          api: _api,
          // New services go out the same way as the ones already offered.
          modes: {for (final s in _services ?? const <OwnerService>[]) ...s.modes}.toList(),
        ),
      ),
    );
    if (added == true) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final services = _services;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.ownerMyServices)),
      floatingActionButton: FloatingActionButton.extended(
        icon: const Icon(Icons.add),
        label: Text(l10n.ownerAddService),
        onPressed: _add,
      ),
      body: services == null
          ? (_error == null ? const LoadingIndicator() : Center(child: Text(_error!, textAlign: TextAlign.center)))
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 88),
              children: [
                if (services.isEmpty) Text(l10n.ownerNoServices, style: AppTextStyles.body2.themed(context)),
                for (final service in services)
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(service.name, style: AppTextStyles.body1),
                    subtitle: Text(
                      '${rupees(service.priceCents / 100)}'
                      '${service.durationMinutes == null ? '' : ' · ${l10n.ownerMinutesShort(service.durationMinutes!)}'}',
                    ),
                    value: service.active,
                    onChanged: (active) => _setActive(service, active),
                  ),
              ],
            ),
    );
  }
}

class _AddServicePage extends StatefulWidget {
  final String shopId;
  final ShopOwnerApi api;
  final List<String> modes;

  const _AddServicePage({required this.shopId, required this.api, required this.modes});

  @override
  State<_AddServicePage> createState() => _AddServicePageState();
}

class _AddServicePageState extends State<_AddServicePage> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _price = TextEditingController();
  final _minutes = TextEditingController(text: '30');
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _price.dispose();
    _minutes.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.addService(
        shopId: widget.shopId,
        name: _name.text.trim(),
        priceCents: int.parse(_price.text.trim()) * 100,
        durationMinutes: int.parse(_minutes.text.trim()),
        modes: widget.modes.isEmpty ? const [modeAtShop] : widget.modes,
      );
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
    return Scaffold(
      appBar: AppBar(title: Text(l10n.ownerAddService)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ServiceFields(name: _name, price: _price, minutes: _minutes),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: AppTextStyles.body2.copyWith(color: AppColors.error)),
              ],
              const SizedBox(height: 20),
              CustomButton(label: l10n.save, isLoading: _saving, onPressed: _saving ? null : _save),
            ],
          ),
        ),
      ),
    );
  }
}

/// When the business is open.
class OwnerHoursPage extends StatefulWidget {
  final String shopId;
  final ShopOwnerApi? api;

  const OwnerHoursPage({super.key, required this.shopId, this.api});

  @override
  State<OwnerHoursPage> createState() => _OwnerHoursPageState();
}

class _OwnerHoursPageState extends State<OwnerHoursPage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  WeekHours? _hours;
  BookingLimits? _limits;
  final _capacity = TextEditingController();
  bool _autoConfirm = false;
  String? _capacityError;
  bool _simplified = false;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final hours = await _api.hours(widget.shopId);
      final limits = await _api.bookingLimits(widget.shopId);
      if (mounted) {
        setState(() {
          _hours = hours;
          _simplified = hours.simplified;
          _limits = limits;
          _capacity.text = limits.capacityOverride?.toString() ?? '';
          _autoConfirm = limits.autoConfirm;
        });
      }
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  @override
  void dispose() {
    _capacity.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final hours = _hours;
    final limits = _limits;
    if (hours == null || limits == null) return;
    final text = _capacity.text.trim();
    final capacity = text.isEmpty ? null : int.tryParse(text);
    if (text.isNotEmpty && (capacity == null || capacity < 1 || capacity > 100)) {
      setState(() => _capacityError = context.l10n.ownerCapacityInvalid);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
      _capacityError = null;
    });
    try {
      // The hours first: confirming by itself only works once they are saved.
      await _api.saveHours(widget.shopId, hours);
      if (capacity != limits.capacityOverride) await _api.saveCapacity(widget.shopId, capacity);
      if (_autoConfirm != limits.autoConfirm) await _api.saveAutoConfirm(widget.shopId, _autoConfirm);
      if (mounted) Navigator.pop(context);
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final hours = _hours;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.ownerOpeningHours)),
      body: hours == null
          ? (_error == null ? const LoadingIndicator() : Center(child: Text(_error!, textAlign: TextAlign.center)))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_simplified) ...[
                    Text(l10n.ownerHoursSimplified, style: AppTextStyles.body2.copyWith(color: AppColors.warning)),
                    const SizedBox(height: 16),
                  ],
                  WeekHoursEditor(hours: hours, onChanged: (value) => setState(() => _hours = value)),
                  const SizedBox(height: 24),
                  Text(l10n.ownerCapacityTitle, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _capacity,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: l10n.ownerCapacityLabel,
                      helperText: l10n.ownerCapacityHelp(_limits?.activeStaff ?? 0),
                      helperMaxLines: 3,
                      errorText: _capacityError,
                    ),
                  ),
                  const SizedBox(height: 8),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(l10n.ownerAutoConfirm),
                    subtitle: Text(l10n.ownerAutoConfirmHelp),
                    value: _autoConfirm,
                    onChanged: (value) => setState(() => _autoConfirm = value),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!, style: AppTextStyles.body2.copyWith(color: AppColors.error)),
                  ],
                  const SizedBox(height: 24),
                  CustomButton(
                    label: l10n.save,
                    isLoading: _saving,
                    onPressed: _saving || !hours.valid ? null : _save,
                  ),
                ],
              ),
            ),
    );
  }
}
