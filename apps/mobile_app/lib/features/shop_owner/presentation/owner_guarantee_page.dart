import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/widgets/custom_button.dart';
import '../../../shared/widgets/custom_text_field.dart';
import '../data/shop_owner_api.dart';

/// "Free-fix guarantee (days)": 0 to 90, with what it means for the customer. Used in setup and settings.
class GuaranteeDaysField extends StatelessWidget {
  final TextEditingController controller;

  const GuaranteeDaysField({super.key, required this.controller});

  static String? validate(String? value, AppLocalizations l10n) {
    final days = int.tryParse((value ?? '').trim());
    return days == null || days < 0 || days > 90 ? l10n.guaranteeInvalid : null;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return CustomTextField(
      key: const ValueKey('guarantee-days'),
      controller: controller,
      label: l10n.guaranteeField,
      helper: l10n.guaranteeHelp,
      keyboardType: TextInputType.number,
      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
      validator: (v) => validate(v, l10n),
    );
  }
}

/// How long after a job the customer may ask for a free fix.
class OwnerGuaranteePage extends StatefulWidget {
  final String shopId;
  final int initialDays;
  final ShopOwnerApi? api;

  const OwnerGuaranteePage({super.key, required this.shopId, required this.initialDays, this.api});

  @override
  State<OwnerGuaranteePage> createState() => _OwnerGuaranteePageState();
}

class _OwnerGuaranteePageState extends State<OwnerGuaranteePage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  final _form = GlobalKey<FormState>();
  late final _days = TextEditingController(text: '${widget.initialDays}');
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _days.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    final messenger = ScaffoldMessenger.of(context);
    final l10n = context.l10n;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await _api.saveGuaranteeDays(widget.shopId, int.parse(_days.text.trim()));
      messenger.showSnackBar(SnackBar(content: Text(l10n.guaranteeSaved)));
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
    return Scaffold(
      appBar: AppBar(title: Text(l10n.guaranteeTitle)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              GuaranteeDaysField(controller: _days),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: AppTextStyles.body2.copyWith(color: context.colors.error)),
              ],
              const SizedBox(height: 24),
              CustomButton(label: l10n.save, isLoading: _saving, onPressed: _saving ? null : _save),
            ],
          ),
        ),
      ),
    );
  }
}
