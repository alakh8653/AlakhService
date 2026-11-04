import 'package:flutter/material.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../data/shop_profile_api.dart';
import 'shop_profile_section.dart';
import '../../../core/network/api_errors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/widgets/error_widget.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../../../shared/widgets/service_card.dart';
import '../../services/domain/entities/service_entity.dart';
import '../../services/presentation/pages/service_detail_page.dart';
import '../data/saved_shops_api.dart';

/// The shops the customer has saved; each opens the list of what it offers, to book again quickly.
class SavedShopsPage extends StatefulWidget {
  final SavedShopsApi? api;

  const SavedShopsPage({super.key, this.api});

  @override
  State<SavedShopsPage> createState() => _SavedShopsPageState();
}

class _SavedShopsPageState extends State<SavedShopsPage> {
  late final SavedShopsApi _api = widget.api ?? sl<SavedShopsApi>();
  List<SavedShop>? _shops;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final shops = await _api.list();
      if (mounted) setState(() => _shops = shops);
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  Future<void> _unsave(SavedShop shop) async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = context.l10n;
    try {
      await _api.unsave(shop.id);
      if (!mounted) return;
      setState(() => _shops = _shops?.where((s) => s.id != shop.id).toList());
      messenger.showSnackBar(SnackBar(content: Text(l10n.shopUnsaved)));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final shops = _shops;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.savedShops)),
      body: shops == null
          ? (_error != null ? AppErrorWidget(message: _error!, onRetry: _load) : const LoadingIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: shops.isEmpty
                  ? ListView(
                      padding: const EdgeInsets.all(32),
                      children: [
                        Icon(Icons.favorite_border, size: 56, color: context.palette.muted),
                        const SizedBox(height: 12),
                        Text(l10n.noSavedShops, textAlign: TextAlign.center, style: AppTextStyles.body2.themed(context)),
                      ],
                    )
                  : ListView.separated(
                      itemCount: shops.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, i) {
                        final shop = shops[i];
                        final details = [
                          if (shop.category.isNotEmpty) shop.category,
                          if (shop.city != null && shop.city!.isNotEmpty) shop.city!,
                          if (shop.ratingCount > 0) '★ ${shop.rating.toStringAsFixed(1)} (${shop.ratingCount})',
                        ].join(' · ');
                        return ListTile(
                          leading: CircleAvatar(
                            backgroundColor: context.colors.primaryContainer,
                            child: Icon(Icons.storefront, color: context.colors.primary),
                          ),
                          title: Text(shop.name),
                          subtitle: details.isEmpty ? null : Text(details),
                          trailing: IconButton(
                            icon: Icon(Icons.favorite, color: context.colors.error),
                            tooltip: l10n.unsaveShop,
                            onPressed: () => _unsave(shop),
                          ),
                          onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => ShopServicesPage(shop: shop, api: widget.api)),
                          ),
                        );
                      },
                    ),
            ),
    );
  }
}

/// What a saved shop offers now; each opens the service, to book it.
/// Where a link its owner shared lands: the business's services, once its name is known. A business that
/// has gone, or is not public, says so rather than showing an empty page.
class SharedShopPage extends StatefulWidget {
  final String shopId;
  final SavedShopsApi? api;

  const SharedShopPage({super.key, required this.shopId, this.api});

  @override
  State<SharedShopPage> createState() => _SharedShopPageState();
}

class _SharedShopPageState extends State<SharedShopPage> {
  late final SavedShopsApi _api = widget.api ?? sl<SavedShopsApi>();
  SavedShop? _shop;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final shop = await _api.shop(widget.shopId);
      if (mounted) setState(() => _shop = shop);
    } on ServerException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final shop = _shop;
    if (shop != null) return ShopServicesPage(shop: shop, api: _api);
    return Scaffold(
      appBar: AppBar(),
      body: _error == null ? const LoadingIndicator() : Center(child: Text(_error!, textAlign: TextAlign.center)),
    );
  }
}

class ShopServicesPage extends StatefulWidget {
  final SavedShop shop;
  final SavedShopsApi? api;

  const ShopServicesPage({super.key, required this.shop, this.api});

  @override
  State<ShopServicesPage> createState() => _ShopServicesPageState();
}

class _ShopServicesPageState extends State<ShopServicesPage> {
  late final SavedShopsApi _api = widget.api ?? sl<SavedShopsApi>();
  List<ServiceEntity>? _services;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final services = await _api.services(widget.shop.id);
      if (mounted) setState(() => _services = services);
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final services = _services;
    return Scaffold(
      appBar: AppBar(title: Text(widget.shop.name)),
      body: services == null
          ? (_error != null ? AppErrorWidget(message: _error!, onRetry: _load) : const LoadingIndicator())
          : services.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text(context.l10n.shopNoServices, textAlign: TextAlign.center, style: AppTextStyles.body2.themed(context)),
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: services.length + 1,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  // First what the business says of itself, for someone arriving from a shared link.
                  itemBuilder: (context, i) => i == 0
                      ? (sl.isRegistered<ShopProfileApi>()
                          ? ShopProfileSection(shopId: widget.shop.id, api: sl<ShopProfileApi>())
                          : const SizedBox.shrink())
                      : ServiceCard(
                          service: services[i - 1],
                          onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => ServiceDetailPage(service: services[i - 1])),
                          ),
                        ),
                ),
    );
  }
}
