import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../data/address_api.dart';
import '../../../../l10n/l10n.dart';

/// Asks for a new address and saves it. Returns the saved address, or null if the customer
/// backed out or saving failed (the failure is shown). Used here and from the booking screen.
Future<SavedAddress?> addAddress(BuildContext context, AddressApi api) async {
  final added = await showDialog<_NewAddress>(context: context, builder: (_) => const _AddressDialog());
  if (added == null || !context.mounted) return null;
  final messenger = ScaffoldMessenger.of(context);
  final savedText = context.l10n.addressSaved;
  try {
    final saved = await api.add(
      label: added.label,
      street: added.street,
      city: added.city,
      state: added.state,
      postalCode: added.postalCode,
    );
    messenger.showSnackBar(SnackBar(content: Text(savedText), backgroundColor: AppColors.success));
    return saved;
  } catch (e) {
    messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    return null;
  }
}

/// The customer's saved addresses: add, remove, and pick the default used when booking.
class AddressesPage extends StatefulWidget {
  final AddressApi? addressApi;

  const AddressesPage({super.key, this.addressApi});

  @override
  State<AddressesPage> createState() => _AddressesPageState();
}

class _AddressesPageState extends State<AddressesPage> {
  late final AddressApi _api = widget.addressApi ?? sl<AddressApi>();
  List<SavedAddress>? _addresses;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final list = await _api.list();
      if (mounted) {
        setState(() {
          _addresses = list;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  Future<void> _run(Future<void> Function() action, String done) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await action();
      messenger.showSnackBar(SnackBar(content: Text(done), backgroundColor: AppColors.success));
      await _load();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    }
  }

  Future<void> _add() async {
    if (await addAddress(context, _api) != null) await _load();
  }

  Future<void> _delete(SavedAddress a) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(context.l10n.deleteAddressQuestion(a.label)),
        content: Text(a.oneLine),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(context.l10n.keepIt)),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: TextButton.styleFrom(foregroundColor: context.colors.error),
            child: Text(context.l10n.delete),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) await _run(() => _api.delete(a.id), context.l10n.addressDeleted);
  }

  @override
  Widget build(BuildContext context) {
    final addresses = _addresses;
    final Widget body;
    if (addresses == null && _error != null) {
      body = AppErrorWidget(message: _error!, onRetry: () {
        setState(() => _error = null);
        _load();
      });
    } else if (addresses == null) {
      body = const Center(child: CircularProgressIndicator());
    } else if (addresses.isEmpty) {
      body = ListView(
        padding: const EdgeInsets.all(32),
        children: [
          const SizedBox(height: 80),
          const Icon(Icons.location_off_outlined, size: 64, color: AppColors.textDisabled),
          const SizedBox(height: 16),
          Text(context.l10n.noAddresses, style: AppTextStyles.subtitle1, textAlign: TextAlign.center),
          const SizedBox(height: 4),
          Text(
            context.l10n.noAddressesBody,
            style: AppTextStyles.body2.themed(context),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          Center(child: CustomButton(label: context.l10n.addAddress, width: 200, leadingIcon: Icons.add, onPressed: _add)),
        ],
      );
    } else {
      body = ListView(
        padding: const EdgeInsets.only(bottom: 88),
        children: [
          for (final a in addresses)
            ListTile(
              leading: Icon(a.isDefault ? Icons.home : Icons.place_outlined, color: context.colors.primary),
              title: Text(a.isDefault ? '${a.label} (default)' : a.label),
              subtitle: Text(a.oneLine),
              trailing: PopupMenuButton<String>(
                tooltip: context.l10n.addressOptions(a.label),
                onSelected: (choice) => choice == 'default'
                    ? _run(() => _api.makeDefault(a.id), context.l10n.defaultAddressSet(a.label))
                    : _delete(a),
                itemBuilder: (_) => [
                  if (!a.isDefault) PopupMenuItem(value: 'default', child: Text(context.l10n.makeDefault)),
                  PopupMenuItem(value: 'delete', child: Text(context.l10n.delete)),
                ],
              ),
            ),
        ],
      );
    }
    return Scaffold(
      appBar: AppBar(title: Text(context.l10n.savedAddresses)),
      floatingActionButton: (addresses?.isNotEmpty ?? false)
          ? FloatingActionButton.extended(
              onPressed: _add,
              icon: const Icon(Icons.add_location_alt_outlined),
              label: Text(context.l10n.addAddress),
            )
          : null,
      body: RefreshIndicator(onRefresh: _load, child: body),
    );
  }
}

class _NewAddress {
  final String label, street, city, state, postalCode;

  const _NewAddress(this.label, this.street, this.city, this.state, this.postalCode);
}

class _AddressDialog extends StatefulWidget {
  const _AddressDialog();

  @override
  State<_AddressDialog> createState() => _AddressDialogState();
}

class _AddressDialogState extends State<_AddressDialog> {
  final _form = GlobalKey<FormState>();
  // The suggested label, in the language on screen; read on first build.
  late final _label = TextEditingController(text: context.l10n.addressDefaultLabel);
  final _street = TextEditingController();
  final _city = TextEditingController();
  final _state = TextEditingController();
  final _pin = TextEditingController();

  @override
  void dispose() {
    for (final c in [_label, _street, _city, _state, _pin]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _required(String? v) => (v == null || v.trim().isEmpty) ? context.l10n.requiredField : null;

  void _save() {
    if (!(_form.currentState?.validate() ?? false)) return;
    Navigator.pop(
      context,
      _NewAddress(_label.text.trim(), _street.text.trim(), _city.text.trim(), _state.text.trim(), _pin.text.trim()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(context.l10n.newAddress),
      content: Form(
        key: _form,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _label,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                decoration: InputDecoration(labelText: context.l10n.addressLabel),
                validator: _required,
              ),
              TextFormField(
                controller: _street,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                autofillHints: const [AutofillHints.streetAddressLine1],
                decoration: InputDecoration(labelText: context.l10n.addressStreet),
                validator: _required,
              ),
              TextFormField(
                controller: _city,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                autofillHints: const [AutofillHints.addressCity],
                decoration: InputDecoration(labelText: context.l10n.city),
                validator: _required,
              ),
              TextFormField(
                controller: _state,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                autofillHints: const [AutofillHints.addressState],
                decoration: InputDecoration(labelText: context.l10n.state),
                validator: _required,
              ),
              TextFormField(
                controller: _pin,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                autofillHints: const [AutofillHints.postalCode],
                inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
                decoration: InputDecoration(labelText: context.l10n.pinCode),
                validator: (v) => RegExp(r'^[1-9]\d{5}$').hasMatch((v ?? '').trim()) ? null : context.l10n.pinInvalid,
                onFieldSubmitted: (_) => _save(),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(context.l10n.cancel)),
        TextButton(onPressed: _save, child: Text(context.l10n.save)),
      ],
    );
  }
}
