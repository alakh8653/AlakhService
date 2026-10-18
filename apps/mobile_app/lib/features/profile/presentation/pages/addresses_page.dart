import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../data/address_api.dart';

/// Asks for a new address and saves it. Returns the saved address, or null if the customer
/// backed out or saving failed (the failure is shown). Used here and from the booking screen.
Future<SavedAddress?> addAddress(BuildContext context, AddressApi api) async {
  final added = await showDialog<_NewAddress>(context: context, builder: (_) => const _AddressDialog());
  if (added == null || !context.mounted) return null;
  final messenger = ScaffoldMessenger.of(context);
  try {
    final saved = await api.add(
      label: added.label,
      street: added.street,
      city: added.city,
      state: added.state,
      postalCode: added.postalCode,
    );
    messenger.showSnackBar(const SnackBar(content: Text('Address saved'), backgroundColor: AppColors.success));
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
        title: Text('Delete "${a.label}"?'),
        content: Text(a.oneLine),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Keep it')),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) await _run(() => _api.delete(a.id), 'Address deleted');
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
          const Text('No saved addresses yet', style: AppTextStyles.subtitle1, textAlign: TextAlign.center),
          const SizedBox(height: 4),
          const Text(
            'Add your home or work address for home visits and pickups.',
            style: AppTextStyles.body2,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          Center(child: CustomButton(label: 'Add address', width: 200, leadingIcon: Icons.add, onPressed: _add)),
        ],
      );
    } else {
      body = ListView(
        padding: const EdgeInsets.only(bottom: 88),
        children: [
          for (final a in addresses)
            ListTile(
              leading: Icon(a.isDefault ? Icons.home : Icons.place_outlined, color: AppColors.primary),
              title: Text(a.isDefault ? '${a.label} (default)' : a.label),
              subtitle: Text(a.oneLine),
              trailing: PopupMenuButton<String>(
                tooltip: 'Options for ${a.label}',
                onSelected: (choice) => choice == 'default'
                    ? _run(() => _api.makeDefault(a.id), '${a.label} is now your default address')
                    : _delete(a),
                itemBuilder: (_) => [
                  if (!a.isDefault) const PopupMenuItem(value: 'default', child: Text('Make default')),
                  const PopupMenuItem(value: 'delete', child: Text('Delete')),
                ],
              ),
            ),
        ],
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Saved addresses')),
      floatingActionButton: (addresses?.isNotEmpty ?? false)
          ? FloatingActionButton.extended(
              onPressed: _add,
              icon: const Icon(Icons.add_location_alt_outlined),
              label: const Text('Add address'),
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
  final _label = TextEditingController(text: 'Home');
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

  String? _required(String? v) => (v == null || v.trim().isEmpty) ? 'Required' : null;

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
      title: const Text('New address'),
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
                decoration: const InputDecoration(labelText: 'Label (Home, Work…)'),
                validator: _required,
              ),
              TextFormField(
                controller: _street,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                autofillHints: const [AutofillHints.streetAddressLine1],
                decoration: const InputDecoration(labelText: 'Flat / house no., street, area'),
                validator: _required,
              ),
              TextFormField(
                controller: _city,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                autofillHints: const [AutofillHints.addressCity],
                decoration: const InputDecoration(labelText: 'City'),
                validator: _required,
              ),
              TextFormField(
                controller: _state,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                autofillHints: const [AutofillHints.addressState],
                decoration: const InputDecoration(labelText: 'State'),
                validator: _required,
              ),
              TextFormField(
                controller: _pin,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                autofillHints: const [AutofillHints.postalCode],
                inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
                decoration: const InputDecoration(labelText: 'PIN code'),
                validator: (v) => RegExp(r'^[1-9]\d{5}$').hasMatch((v ?? '').trim()) ? null : 'Enter a 6-digit PIN code',
                onFieldSubmitted: (_) => _save(),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        TextButton(onPressed: _save, child: const Text('Save')),
      ],
    );
  }
}
