import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:location/location.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../features/auth/domain/entities/user.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/widgets/custom_button.dart';
import '../../../shared/widgets/custom_text_field.dart';
import '../../../shared/widgets/location_rationale.dart';
import '../data/shop_owner_api.dart';
import 'business_categories.dart';
import 'verification_page.dart';
import 'week_hours_editor.dart';

/// Where the device is, for placing the business on the map; null when unknown or refused.
typedef FindLocation = Future<({double latitude, double longitude})?> Function(BuildContext context);

Future<({double latitude, double longitude})?> _deviceLocation(BuildContext context) async {
  final location = Location();
  if (!await location.serviceEnabled() && !await location.requestService()) return null;
  var permission = await location.hasPermission();
  if (permission == PermissionStatus.denied) {
    if (!context.mounted || !await explainLocation(LocationPurpose.business, context: context)) return null;
    permission = await location.requestPermission();
  }
  if (permission != PermissionStatus.granted && permission != PermissionStatus.grantedLimited) return null;
  final fix = await location.getLocation().timeout(const Duration(seconds: 15));
  return (latitude: fix.latitude, longitude: fix.longitude);
}

class _ServiceDraft {
  final name = TextEditingController();
  final price = TextEditingController();
  final minutes = TextEditingController(text: '30');

  void dispose() {
    name.dispose();
    price.dispose();
    minutes.dispose();
  }
}

/// A shop owner or a person working alone gets on the app in three short steps: who and where they are,
/// what they offer, when they work. Verification comes next, and can wait.
class ShopSetupPage extends StatefulWidget {
  final User user;
  final ShopOwnerApi? api;
  final FindLocation? findLocation;

  const ShopSetupPage({super.key, required this.user, this.api, this.findLocation});

  @override
  State<ShopSetupPage> createState() => _ShopSetupPageState();
}

class _ShopSetupPageState extends State<ShopSetupPage> {
  late final ShopOwnerApi _api = widget.api ?? sl<ShopOwnerApi>();
  final _businessForm = GlobalKey<FormState>();
  final _servicesForm = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.user.name);
  final _city = TextEditingController();
  final _address = TextEditingController();
  late final _phone = TextEditingController(text: widget.user.phone);
  final List<_ServiceDraft> _drafts = [_ServiceDraft()];
  // Nothing chosen for them: a default here would quietly list an electrician as a salon.
  String? _category;
  bool _atShop = false;
  bool _atHome = false;
  ({double latitude, double longitude})? _position;
  WeekHours _hours = WeekHours.suggested;
  int _step = 0;
  bool _locating = false;
  bool _saving = false;
  String? _error;

  // What the server already has, so that trying again after a failure repeats nothing.
  String? _shopId;
  int _servicesSaved = 0;

  @override
  void dispose() {
    _name.dispose();
    _city.dispose();
    _address.dispose();
    _phone.dispose();
    for (final draft in _drafts) {
      draft.dispose();
    }
    super.dispose();
  }

  Future<void> _useLocation() async {
    setState(() => _locating = true);
    ({double latitude, double longitude})? found;
    try {
      found = await (widget.findLocation ?? _deviceLocation)(context);
    } catch (_) {
      found = null;
    }
    if (!mounted) return;
    setState(() {
      _locating = false;
      _position = found ?? _position;
    });
    if (found == null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.l10n.ownerLocationFailed)));
    }
  }

  void _next() {
    final form = _step == 0 ? _businessForm : _servicesForm;
    if (!(form.currentState?.validate() ?? false)) return;
    if (_step == 0 && !_atShop && !_atHome) {
      setState(() => _error = context.l10n.ownerChooseWhere);
      return;
    }
    setState(() {
      _error = null;
      _step++;
    });
  }

  List<String> get _modes => [if (_atShop) modeAtShop, if (_atHome) modeAtHome];

  Future<void> _finish() async {
    if (!_hours.valid) {
      setState(() => _error = context.l10n.ownerHoursInvalid);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final shopId = _shopId ??= (await _api.createShop(
        ownerId: widget.user.id,
        name: _name.text.trim(),
        category: _category!,
        city: _city.text.trim(),
        address: _address.text.trim(),
        phone: _phone.text.trim(),
        latitude: _position?.latitude,
        longitude: _position?.longitude,
      ))
          .id;
      for (; _servicesSaved < _drafts.length; _servicesSaved++) {
        final draft = _drafts[_servicesSaved];
        await _api.addService(
          shopId: shopId,
          name: draft.name.text.trim(),
          priceCents: int.parse(draft.price.text.trim()) * 100,
          durationMinutes: int.parse(draft.minutes.text.trim()),
          modes: _modes,
        );
      }
      await _api.saveHours(shopId, _hours);
      await _api.ensureOwnerIsStaff(shopId, widget.user.id, widget.user.name, phone: widget.user.phone);
      await OwnerIntent.save(true);
      if (!mounted) return;
      await Navigator.pushReplacement<void, void>(
        context,
        MaterialPageRoute(builder: (_) => VerificationPage(shopId: shopId, firstTime: true, api: _api)),
      );
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _close() async {
    // They changed their mind for now: the app stops asking, and Profile still offers it.
    await OwnerIntent.save(false);
    if (mounted) Navigator.pop(context);
  }

  Widget _businessStep(AppLocalizations l10n) => Form(
        key: _businessForm,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CustomTextField(
              controller: _name,
              label: l10n.ownerBusinessName,
              helper: l10n.ownerBusinessNameHelp,
              textCapitalization: TextCapitalization.words,
              validator: (v) => (v ?? '').trim().isEmpty ? l10n.ownerRequired : null,
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _category,
              isExpanded: true,
              decoration: InputDecoration(labelText: l10n.ownerCategory),
              validator: (value) => value == null ? l10n.ownerRequired : null,
              items: [
                for (final category in businessCategories)
                  DropdownMenuItem(value: category, child: Text(businessCategoryLabel(category, l10n))),
              ],
              onChanged: (value) => setState(() => _category = value),
            ),
            const SizedBox(height: 16),
            Text(l10n.ownerWhereDoYouWork, style: AppTextStyles.body2.themed(context)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                FilterChip(
                  avatar: const Icon(Icons.storefront_outlined, size: 18),
                  label: Text(l10n.ownerAtMyShop),
                  selected: _atShop,
                  onSelected: (on) => setState(() => _atShop = on),
                ),
                FilterChip(
                  avatar: const Icon(Icons.home_outlined, size: 18),
                  label: Text(l10n.ownerAtCustomersHome),
                  selected: _atHome,
                  onSelected: (on) => setState(() => _atHome = on),
                ),
              ],
            ),
            const SizedBox(height: 16),
            CustomTextField(
              controller: _city,
              label: l10n.ownerCity,
              textCapitalization: TextCapitalization.words,
              validator: (v) => (v ?? '').trim().isEmpty ? l10n.ownerRequired : null,
            ),
            const SizedBox(height: 16),
            CustomTextField(
              controller: _address,
              label: _atShop ? l10n.ownerShopAddress : l10n.ownerAreaYouServe,
              maxLines: 2,
              textCapitalization: TextCapitalization.sentences,
              validator: (v) => _atShop && (v ?? '').trim().isEmpty ? l10n.ownerRequired : null,
            ),
            const SizedBox(height: 16),
            CustomTextField(controller: _phone, label: l10n.ownerPhone, keyboardType: TextInputType.phone),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              icon: _position == null
                  ? const Icon(Icons.my_location)
                  : const Icon(Icons.check_circle, color: AppColors.success),
              label: Text(_position == null ? l10n.ownerUseLocation : l10n.ownerLocationSaved),
              onPressed: _locating ? null : _useLocation,
            ),
          ],
        ),
      );

  Widget _servicesStep(AppLocalizations l10n) => Form(
        key: _servicesForm,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.ownerServicesHelp, style: AppTextStyles.body2.themed(context)),
            const SizedBox(height: 16),
            for (var i = 0; i < _drafts.length; i++) ...[
              ServiceFields(
                key: ObjectKey(_drafts[i]),
                name: _drafts[i].name,
                price: _drafts[i].price,
                minutes: _drafts[i].minutes,
                readOnly: i < _servicesSaved,
                onRemove: i > 0 && i >= _servicesSaved
                    ? () => setState(() => _drafts.removeAt(i).dispose())
                    : null,
              ),
              const SizedBox(height: 16),
            ],
            TextButton.icon(
              icon: const Icon(Icons.add),
              label: Text(l10n.ownerAddAnotherService),
              onPressed: () => setState(() => _drafts.add(_ServiceDraft())),
            ),
          ],
        ),
      );

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final titles = [l10n.ownerStepBusiness, l10n.ownerStepServices, l10n.ownerStepHours];
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.ownerSetupTitle),
        leading: _step == 0
            ? IconButton(icon: const Icon(Icons.close), tooltip: l10n.notNow, onPressed: _saving ? null : _close)
            : IconButton(
                icon: const Icon(Icons.arrow_back),
                tooltip: MaterialLocalizations.of(context).backButtonTooltip,
                onPressed: _saving ? null : () => setState(() => _step--),
              ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              LinearProgressIndicator(value: (_step + 1) / 3),
              const SizedBox(height: 12),
              Text(l10n.ownerStepOf(_step + 1, 3), style: AppTextStyles.caption.themed(context)),
              const SizedBox(height: 4),
              Text(titles[_step], style: AppTextStyles.heading2),
              const SizedBox(height: 20),
              switch (_step) {
                0 => _businessStep(l10n),
                1 => _servicesStep(l10n),
                _ => WeekHoursEditor(hours: _hours, onChanged: (hours) => setState(() => _hours = hours)),
              },
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: AppTextStyles.body2.copyWith(color: AppColors.error)),
              ],
              const SizedBox(height: 24),
              CustomButton(
                label: _step == 2 ? l10n.ownerFinishSetup : l10n.continueLabel,
                isLoading: _saving,
                onPressed: _saving ? null : (_step == 2 ? _finish : _next),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A service's name, price in rupees and time it takes; used in setup and when adding one later.
class ServiceFields extends StatelessWidget {
  final TextEditingController name;
  final TextEditingController price;
  final TextEditingController minutes;
  final bool readOnly;
  final VoidCallback? onRemove;

  const ServiceFields({
    super.key,
    required this.name,
    required this.price,
    required this.minutes,
    this.readOnly = false,
    this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    String? whole(String? v) => (int.tryParse((v ?? '').trim()) ?? 0) <= 0 ? l10n.ownerEnterNumber : null;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: context.palette.muted.withValues(alpha: 0.3)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: CustomTextField(
                  controller: name,
                  label: l10n.ownerServiceName,
                  hint: l10n.ownerServiceNameHint,
                  readOnly: readOnly,
                  textCapitalization: TextCapitalization.sentences,
                  validator: (v) => (v ?? '').trim().isEmpty ? l10n.ownerRequired : null,
                ),
              ),
              if (onRemove != null)
                IconButton(icon: const Icon(Icons.delete_outline), tooltip: l10n.delete, onPressed: onRemove),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: CustomTextField(
                  controller: price,
                  label: l10n.ownerPrice,
                  prefixText: '₹ ',
                  readOnly: readOnly,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  validator: whole,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: CustomTextField(
                  controller: minutes,
                  label: l10n.ownerMinutes,
                  readOnly: readOnly,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  validator: whole,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
