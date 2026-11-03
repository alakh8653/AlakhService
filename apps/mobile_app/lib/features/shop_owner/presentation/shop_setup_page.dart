import 'package:flutter/foundation.dart' show listEquals;
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
import '../../../shared/service_types.dart';
import '../../../shared/widgets/custom_button.dart';
import '../../../shared/widgets/custom_text_field.dart';
import '../../../shared/widgets/location_rationale.dart';
import '../data/shop_owner_api.dart';
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
  /// Which of the business's types of work this goes under.
  String typeId;
  final name = TextEditingController();
  final price = TextEditingController();
  final TextEditingController minutes;

  _ServiceDraft(this.typeId, int usualMinutes) : minutes = TextEditingController(text: '$usualMinutes');

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
  final _samePrice = TextEditingController();
  final List<_ServiceDraft> _drafts = [];
  // Nothing chosen for them: a default here would quietly list an electrician as a salon.
  String? _category;
  // An electrician who is also a plumber: found under both, with the documents of both.
  final List<String> _otherTypes = [];
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
  List<String> _typesSaved = const [];
  int _servicesSaved = 0;

  @override
  void dispose() {
    _name.dispose();
    _city.dispose();
    _address.dispose();
    _phone.dispose();
    _samePrice.dispose();
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
    if (_step == 1 && _drafts.isEmpty) {
      setState(() => _error = context.l10n.ownerPickOneService);
      return;
    }
    if (_step == 1) {
      // A type with nothing under it would never be found by customers browsing it.
      for (final id in _otherTypes) {
        if (!_drafts.any((d) => d.typeId == id)) {
          final name = serviceTypeById(id)?.label(context.l10n) ?? id;
          setState(() => _error = context.l10n.ownerPickServiceFor(name));
          return;
        }
      }
    }
    setState(() {
      _error = null;
      _step++;
    });
  }

  List<String> get _modes => [if (_atShop) modeAtShop, if (_atHome) modeAtHome];

  ServiceType? get _type => serviceTypeById(_category ?? '');

  List<String> get _typeIds => [if (_category != null) _category!, ..._otherTypes];

  List<String> _suggestionsOf(String typeId) => serviceTypeById(typeId)?.suggestions ?? const [];

  _ServiceDraft _newDraft(String typeId, {String name = ''}) =>
      _ServiceDraft(typeId, usualMinutes(serviceTypeById(typeId)))
        ..name.text = name
        ..price.text = _samePrice.text.trim();

  int _draftIndex(String typeId, String name) => _drafts
      .indexWhere((d) => d.typeId == typeId && d.name.text.trim().toLowerCase() == name.toLowerCase());

  void _toggle(String typeId, String name, bool on) {
    setState(() {
      _error = null;
      final at = _draftIndex(typeId, name);
      if (on && at < 0) _drafts.add(_newDraft(typeId, name: name));
      // What the server already has stays.
      if (!on && at >= _servicesSaved) _drafts.removeAt(at).dispose();
    });
  }

  bool _allSelected(String typeId) {
    final suggestions = _suggestionsOf(typeId);
    return suggestions.isNotEmpty && suggestions.every((name) => _draftIndex(typeId, name) >= 0);
  }

  void _selectAll(String typeId, bool on) {
    for (final name in _suggestionsOf(typeId)) {
      _toggle(typeId, name, on);
    }
  }

  void _applySamePrice(String value) {
    setState(() {
      for (final draft in _drafts.skip(_servicesSaved)) {
        draft.price.text = value.trim();
      }
    });
  }

  /// That type's services are gone, except what the server already has, which goes under the main type.
  void _dropDraftsOf(String? typeId) {
    for (var i = _drafts.length - 1; i >= 0; i--) {
      if (_drafts[i].typeId != typeId) continue;
      if (i >= _servicesSaved) {
        _drafts.removeAt(i).dispose();
      } else {
        _drafts[i].typeId = _category!;
      }
    }
  }

  Future<void> _chooseType() async {
    final chosen = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (_) => const _TypePicker(),
    );
    if (chosen == null || chosen == _category || !mounted) return;
    setState(() {
      final last = _category;
      _category = chosen;
      _otherTypes.remove(chosen);
      // The last type's services are not this one's.
      _dropDraftsOf(last);
    });
  }

  Future<void> _addOtherType() async {
    final chosen = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _TypePicker(leaveOut: _typeIds.toSet()),
    );
    if (chosen == null || !mounted) return;
    setState(() {
      _error = null;
      _otherTypes.add(chosen);
    });
  }

  void _removeOtherType(String id) {
    setState(() {
      _otherTypes.remove(id);
      _dropDraftsOf(id);
    });
  }

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
      final types = _typeIds;
      final String shopId;
      if (_shopId == null) {
        shopId = _shopId = (await _api.createShop(
          ownerId: widget.user.id,
          name: _name.text.trim(),
          category: _category!,
          otherTypes: _otherTypes,
          city: _city.text.trim(),
          address: _address.text.trim(),
          phone: _phone.text.trim(),
          latitude: _position?.latitude,
          longitude: _position?.longitude,
        ))
            .id;
      } else {
        shopId = _shopId!;
        // They went back after a failure and changed their types: the services below go under the new ones.
        if (!listEquals(types, _typesSaved)) {
          await _api.setTypes(shopId, category: _category!, otherTypes: _otherTypes);
        }
      }
      _typesSaved = types;
      for (; _servicesSaved < _drafts.length; _servicesSaved++) {
        final draft = _drafts[_servicesSaved];
        await _api.addService(
          shopId: shopId,
          name: draft.name.text.trim(),
          priceCents: int.parse(draft.price.text.trim()) * 100,
          durationMinutes: int.parse(draft.minutes.text.trim()),
          modes: _modes,
          // With one type of work the service simply follows the shop.
          serviceType: _otherTypes.isEmpty ? null : draft.typeId,
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
            FormField<String>(
              key: ValueKey('type-${_category ?? ''}'),
              initialValue: _category,
              validator: (value) => value == null ? l10n.ownerRequired : null,
              builder: (field) => InkWell(
                key: const ValueKey('pick-type'),
                onTap: _chooseType,
                child: InputDecorator(
                  decoration: InputDecoration(
                    labelText: l10n.ownerCategory,
                    errorText: field.errorText,
                    suffixIcon: const Icon(Icons.search),
                  ),
                  child: Text(_type?.label(l10n) ?? l10n.ownerChooseType),
                ),
              ),
            ),
            if (_category != null) ...[
              if (_otherTypes.isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: [
                    for (final id in _otherTypes)
                      InputChip(
                        avatar: Icon(serviceTypeById(id)?.icon, size: 18),
                        label: Text(serviceTypeById(id)?.label(l10n) ?? id),
                        onDeleted: () => _removeOtherType(id),
                      ),
                  ],
                ),
                Text(l10n.ownerOtherTypesHelp, style: AppTextStyles.caption.themed(context)),
              ],
              if (_otherTypes.length < maxOtherTypes)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    key: const ValueKey('add-type'),
                    icon: const Icon(Icons.add),
                    label: Text(l10n.ownerAddAnotherType),
                    onPressed: _addOtherType,
                  ),
                ),
            ],
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
            Text(l10n.ownerPickServices, style: AppTextStyles.body2.themed(context)),
            const SizedBox(height: 12),
            for (final typeId in _typeIds) ..._servicesOf(typeId, l10n),
          ],
        ),
      );

  /// One type of work's services to tap; with several types, each has its own heading.
  List<Widget> _servicesOf(String typeId, AppLocalizations l10n) {
    final isMain = typeId == _category;
    final suggestions = _suggestionsOf(typeId);
    final allSelected = _allSelected(typeId);
    return [
      if (_otherTypes.isNotEmpty) ...[
        Text(serviceTypeById(typeId)?.label(l10n) ?? typeId, style: AppTextStyles.heading3),
        const SizedBox(height: 4),
      ],
      if (suggestions.isNotEmpty) ...[
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            key: ValueKey(isMain ? 'select-all-services' : 'select-all-services-$typeId'),
            icon: Icon(allSelected ? Icons.deselect : Icons.select_all),
            label: Text(allSelected ? l10n.ownerClearAll : l10n.ownerSelectAll),
            onPressed: () => _selectAll(typeId, !allSelected),
          ),
        ),
        Wrap(
          spacing: 8,
          children: [
            for (final name in suggestions)
              FilterChip(
                label: Text(name),
                selected: _draftIndex(typeId, name) >= 0,
                onSelected: (on) => _toggle(typeId, name, on),
              ),
          ],
        ),
        const SizedBox(height: 12),
      ],
      if (isMain && _drafts.isNotEmpty) ...[
        CustomTextField(
          controller: _samePrice,
          label: l10n.ownerSamePrice,
          helper: l10n.ownerSamePriceHelp,
          keyboardType: TextInputType.number,
          onChanged: _applySamePrice,
        ),
        const SizedBox(height: 16),
      ],
      for (var i = 0; i < _drafts.length; i++)
        if (_drafts[i].typeId == typeId) ...[
          ServiceFields(
            key: ObjectKey(_drafts[i]),
            name: _drafts[i].name,
            price: _drafts[i].price,
            minutes: _drafts[i].minutes,
            readOnly: i < _servicesSaved,
            onRemove: i >= _servicesSaved ? () => setState(() => _drafts.removeAt(i).dispose()) : null,
          ),
          const SizedBox(height: 16),
        ],
      Align(
        alignment: Alignment.centerLeft,
        child: TextButton.icon(
          icon: const Icon(Icons.add),
          label: Text(l10n.ownerAddAnotherService),
          onPressed: () => setState(() => _drafts.add(_newDraft(typeId))),
        ),
      ),
      const SizedBox(height: 8),
    ];
  }

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

/// Every kind of work, grouped, with a search, because nobody should have to scroll past fifty to find theirs.
class _TypePicker extends StatefulWidget {
  /// Types the business already has.
  final Set<String> leaveOut;

  const _TypePicker({this.leaveOut = const {}});

  @override
  State<_TypePicker> createState() => _TypePickerState();
}

class _TypePickerState extends State<_TypePicker> {
  String _query = '';

  bool _matches(ServiceType type, AppLocalizations l10n) {
    final q = _query.trim().toLowerCase();
    if (q.isEmpty) return true;
    // By what they do too: "AC" finds appliance repair, "mason" finds construction.
    return type.label(l10n).toLowerCase().contains(q) ||
        type.id.replaceAll('_', ' ').contains(q) ||
        type.suggestions.any((name) => name.toLowerCase().contains(q));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final found =
        serviceTypes.where((type) => !widget.leaveOut.contains(type.id) && _matches(type, l10n)).toList();
    return SafeArea(
      child: SizedBox(
        height: MediaQuery.sizeOf(context).height * 0.85,
        child: Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, MediaQuery.viewInsetsOf(context).bottom),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l10n.ownerChooseType, style: AppTextStyles.heading3),
              const SizedBox(height: 8),
              TextField(
                key: const ValueKey('search-type'),
                decoration: InputDecoration(hintText: l10n.ownerSearchType, prefixIcon: const Icon(Icons.search)),
                onChanged: (value) => setState(() => _query = value),
              ),
              Expanded(
                child: ListView(
                  children: [
                    for (final group in ServiceGroup.values)
                      if (found.any((type) => type.group == group)) ...[
                        Padding(
                          padding: const EdgeInsets.only(top: 12, bottom: 4),
                          child: Text(serviceGroupLabel(group, l10n), style: AppTextStyles.caption.themed(context)),
                        ),
                        for (final type in found.where((t) => t.group == group))
                          ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: Icon(type.icon),
                            title: Text(type.label(l10n), style: AppTextStyles.body1),
                            onTap: () => Navigator.pop(context, type.id),
                          ),
                      ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
