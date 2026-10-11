import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../data/address_api.dart';

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

  Future<void> _run(Future<void> Function() action) async {
    try {
      await action();
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
        );
      }
    }
  }

  Future<void> _add() async {
    final added = await showDialog<_NewAddress>(context: context, builder: (_) => const _AddressDialog());
    if (added == null) return;
    await _run(() => _api.add(
          label: added.label,
          street: added.street,
          city: added.city,
          state: added.state,
          postalCode: added.postalCode,
        ));
  }

  @override
  Widget build(BuildContext context) {
    final addresses = _addresses;
    return Scaffold(
      appBar: AppBar(title: const Text('Saved addresses')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _add,
        icon: const Icon(Icons.add_location_alt_outlined),
        label: const Text('Add address'),
      ),
      body: addresses == null
          ? Center(child: _error == null ? const CircularProgressIndicator() : Text(_error!))
          : addresses.isEmpty
              ? const Center(child: Text('No saved addresses yet.', style: AppTextStyles.subtitle1))
              : ListView(
                  padding: const EdgeInsets.only(bottom: 88),
                  children: [
                    for (final a in addresses)
                      ListTile(
                        leading: Icon(a.isDefault ? Icons.home : Icons.place_outlined, color: AppColors.primary),
                        title: Text(a.isDefault ? '${a.label} (default)' : a.label),
                        subtitle: Text(a.oneLine),
                        trailing: PopupMenuButton<String>(
                          onSelected: (choice) => _run(
                            () => choice == 'default' ? _api.makeDefault(a.id) : _api.delete(a.id),
                          ),
                          itemBuilder: (_) => [
                            if (!a.isDefault) const PopupMenuItem(value: 'default', child: Text('Make default')),
                            const PopupMenuItem(value: 'delete', child: Text('Delete')),
                          ],
                        ),
                      ),
                  ],
                ),
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
              TextFormField(controller: _label, decoration: const InputDecoration(labelText: 'Label (Home, Work…)'), validator: _required),
              TextFormField(controller: _street, decoration: const InputDecoration(labelText: 'House / street'), validator: _required),
              TextFormField(controller: _city, decoration: const InputDecoration(labelText: 'City'), validator: _required),
              TextFormField(controller: _state, decoration: const InputDecoration(labelText: 'State'), validator: _required),
              TextFormField(
                controller: _pin,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'PIN code'),
                validator: (v) => RegExp(r'^\d{6}$').hasMatch((v ?? '').trim()) ? null : 'Enter a 6-digit PIN code',
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        TextButton(
          onPressed: () {
            if (!(_form.currentState?.validate() ?? false)) return;
            Navigator.pop(
              context,
              _NewAddress(_label.text.trim(), _street.text.trim(), _city.text.trim(), _state.text.trim(), _pin.text.trim()),
            );
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}
