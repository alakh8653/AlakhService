import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../shared/service_types.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../../shared/widgets/service_card.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../../jobs/data/location_reporter.dart';
import '../../../profile/presentation/pages/display_settings.dart' show showChoiceSheet;
import '../../../../shared/widgets/location_rationale.dart';
import '../../domain/entities/service_entity.dart';
import '../../domain/entities/service_filters.dart';
import '../bloc/service_bloc.dart';
import '../bloc/service_event.dart';
import '../bloc/service_state.dart';
import 'service_detail_page.dart';
import '../../../../l10n/l10n.dart';

class ServiceListPage extends StatefulWidget {
  /// Search to run on open (e.g. a category picked on the home screen).
  final String? initialQuery;

  /// Shows only this type of service (a tile picked on the home screen).
  final ServiceType? type;

  /// How long typing must pause before searching, so each keystroke isn't a request.
  final Duration debounce;

  /// Where the phone is (latitude, longitude), for "Nearest"; null if the customer says no. The device's
  /// location by default.
  final Future<(double, double)?> Function()? locate;

  const ServiceListPage({
    super.key,
    this.initialQuery,
    this.type,
    this.debounce = const Duration(milliseconds: 350),
    this.locate,
  });

  @override
  State<ServiceListPage> createState() => _ServiceListPageState();
}

class _ServiceListPageState extends State<ServiceListPage> {
  final _searchController = TextEditingController();
  Timer? _debounce;

  String get _query => _searchController.text.trim();
  late ServiceType? _type = widget.type;
  ServiceFilters _filters = ServiceFilters.none;

  /// Price limits on offer, in rupees.
  static const _priceLimits = [300.0, 500.0, 1000.0, 2000.0];

  @override
  void initState() {
    super.initState();
    _searchController.text = widget.initialQuery?.trim() ?? '';
    _search();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _search() {
    _debounce?.cancel();
    context.read<ServiceBloc>().add(
          _query.isEmpty
              ? LoadServices(category: _type?.id, filters: _filters)
              : SearchServices(query: _query, category: _type?.id, filters: _filters),
        );
  }

  void _onChanged(String _) {
    setState(() {}); // shows or hides the clear button
    _debounce?.cancel();
    _debounce = Timer(widget.debounce, _search);
  }

  void _clear() {
    _searchController.clear();
    setState(() {});
    _search();
  }

  void _setFilters(ServiceFilters filters) {
    setState(() => _filters = filters);
    _search();
  }

  Future<(double, double)?> _locate() async {
    final custom = widget.locate;
    if (custom != null) return custom();
    try {
      final fix = await DeviceLocationSource(purpose: LocationPurpose.nearby).current();
      return fix == null ? null : (fix.latitude, fix.longitude);
    } catch (_) {
      return null;
    }
  }

  String _sortLabel(AppLocalizations l10n, ServiceSort sort) => switch (sort) {
        ServiceSort.recommended => l10n.sortRecommended,
        ServiceSort.nearest => l10n.sortNearest,
        ServiceSort.priceLow => l10n.sortPriceLow,
        ServiceSort.priceHigh => l10n.sortPriceHigh,
        ServiceSort.topRated => l10n.sortTopRated,
      };

  Future<void> _chooseSort() async {
    final l10n = context.l10n;
    final sort = await showChoiceSheet<ServiceSort>(
      context,
      title: l10n.sortLabel,
      selected: _filters.sort,
      options: [for (final s in ServiceSort.values) (s, _sortLabel(l10n, s))],
    );
    if (sort == null || !mounted) return;
    if (sort == ServiceSort.nearest && !_filters.located) {
      final messenger = ScaffoldMessenger.of(context);
      final place = await _locate();
      if (!mounted) return;
      if (place == null) {
        messenger.showSnackBar(SnackBar(content: Text(l10n.nearestNeedsLocation)));
        return;
      }
      _setFilters(_filters.copyWith(sort: sort, at: () => place));
      return;
    }
    _setFilters(_filters.copyWith(sort: sort));
  }

  Future<void> _choosePrice() async {
    final l10n = context.l10n;
    // A record, so "Any price" (no limit) can be told apart from dismissing the sheet.
    final picked = await showChoiceSheet<(double?,)>(
      context,
      title: l10n.filterPriceTitle,
      selected: (_filters.maxPrice,),
      options: [
        ((null,), l10n.filterPriceAny),
        for (final p in _priceLimits) ((p,), l10n.filterPriceUnder(p.round())),
      ],
    );
    if (picked != null && mounted) _setFilters(_filters.copyWith(maxPrice: () => picked.$1));
  }

  Widget _filterBar(AppLocalizations l10n) {
    final f = _filters;
    return SizedBox(
      height: 48,
      child: ListView(
        key: const ValueKey('service-filters'),
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          ActionChip(
            key: const ValueKey('filter-sort'),
            avatar: const Icon(Icons.sort, size: 18),
            label: Text(f.sort == ServiceSort.recommended ? l10n.sortLabel : _sortLabel(l10n, f.sort)),
            onPressed: _chooseSort,
          ),
          const SizedBox(width: 8),
          FilterChip(
            key: const ValueKey('filter-home-visit'),
            label: Text(l10n.filterHomeVisit),
            selected: f.homeVisit,
            onSelected: (on) => _setFilters(f.copyWith(homeVisit: on)),
          ),
          const SizedBox(width: 8),
          FilterChip(
            key: const ValueKey('filter-rating'),
            label: Text(l10n.filterRating4),
            selected: f.minRating != null,
            onSelected: (on) => _setFilters(f.copyWith(minRating: () => on ? 4.0 : null)),
          ),
          const SizedBox(width: 8),
          ActionChip(
            key: const ValueKey('filter-price'),
            avatar: Icon(f.maxPrice == null ? Icons.currency_rupee : Icons.check, size: 18),
            label: Text(f.maxPrice == null ? l10n.filterPriceTitle : l10n.filterPriceUnder(f.maxPrice!.round())),
            onPressed: _choosePrice,
          ),
          if (f.count > 0 || f.sort != ServiceSort.recommended) ...[
            const SizedBox(width: 8),
            TextButton(
              key: const ValueKey('filter-clear'),
              onPressed: () => _setFilters(ServiceFilters.none),
              child: Text(l10n.filterClearAll),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _refresh() async {
    final bloc = context.read<ServiceBloc>();
    final done = bloc.stream.firstWhere((s) => s is! ServiceLoading);
    _search();
    await done;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.servicesTitle)),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _searchController,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                hintText: l10n.searchHint,
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        tooltip: l10n.clearSearch,
                        icon: const Icon(Icons.clear),
                        onPressed: _clear,
                      )
                    : null,
              ),
              onChanged: _onChanged,
              onSubmitted: (_) => _search(),
            ),
          ),
          if (_type case final type?)
            Padding(
              padding: const EdgeInsets.only(left: 16, right: 16, bottom: 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: InputChip(
                  key: const ValueKey('service-type-filter'),
                  avatar: Icon(type.icon, size: 18),
                  label: Text(l10n.servicesShowingType(type.label(l10n))),
                  onDeleted: () {
                    setState(() => _type = null);
                    _search();
                  },
                ),
              ),
            ),
          _filterBar(l10n),
          const SizedBox(height: 4),
          Expanded(
            child: BlocBuilder<ServiceBloc, ServiceState>(
              builder: (context, state) {
                if (state is ServiceLoading || state is ServiceInitial) {
                  return LoadingIndicator(message: l10n.loadingServices);
                }
                if (state is ServiceError) {
                  return AppErrorWidget(message: state.message, onRetry: _search);
                }
                final services = switch (state) {
                  ServicesLoaded(:final services) => services,
                  ServiceSearchResults(:final results) => results,
                  _ => <ServiceEntity>[],
                };
                if (services.isEmpty) {
                  return RefreshIndicator(
                    onRefresh: _refresh,
                    child: ListView(
                      padding: const EdgeInsets.all(32),
                      children: [
                        const SizedBox(height: 48),
                        const Icon(Icons.search_off, size: 64, color: AppColors.textDisabled),
                        const SizedBox(height: 16),
                        Text(
                          _filters.count > 0
                              ? l10n.noMatchesFilters
                              : _query.isEmpty
                                  ? l10n.noServicesListed
                                  : l10n.nothingFound(_query),
                          style: AppTextStyles.subtitle1,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _query.isEmpty ? l10n.pullToCheck : l10n.tryDifferentWord,
                          style: AppTextStyles.body2.themed(context),
                          textAlign: TextAlign.center,
                        ),
                        if (_filters.count > 0) ...[
                          const SizedBox(height: 16),
                          Center(
                            child: OutlinedButton(
                              onPressed: () => _setFilters(ServiceFilters.none),
                              child: Text(l10n.filterClearAll),
                            ),
                          ),
                        ] else if (_query.isNotEmpty) ...[
                          const SizedBox(height: 16),
                          Center(child: OutlinedButton(onPressed: _clear, child: Text(l10n.showAllServices))),
                        ],
                      ],
                    ),
                  );
                }
                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                    itemCount: services.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (context, index) {
                      final service = services[index];
                      return ServiceCard(
                        service: service,
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => ServiceDetailPage(service: service)),
                        ),
                      );
                    },
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
