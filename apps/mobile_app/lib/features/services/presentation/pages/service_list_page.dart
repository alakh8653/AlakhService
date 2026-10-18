import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../../shared/widgets/service_card.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../domain/entities/service_entity.dart';
import '../bloc/service_bloc.dart';
import '../bloc/service_event.dart';
import '../bloc/service_state.dart';
import 'service_detail_page.dart';

class ServiceListPage extends StatefulWidget {
  /// Search to run on open (e.g. a category picked on the home screen).
  final String? initialQuery;

  /// How long typing must pause before searching, so each keystroke isn't a request.
  final Duration debounce;

  const ServiceListPage({super.key, this.initialQuery, this.debounce = const Duration(milliseconds: 350)});

  @override
  State<ServiceListPage> createState() => _ServiceListPageState();
}

class _ServiceListPageState extends State<ServiceListPage> {
  final _searchController = TextEditingController();
  Timer? _debounce;

  String get _query => _searchController.text.trim();

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
    context.read<ServiceBloc>().add(_query.isEmpty ? const LoadServices() : SearchServices(query: _query));
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

  Future<void> _refresh() async {
    final bloc = context.read<ServiceBloc>();
    final done = bloc.stream.firstWhere((s) => s is! ServiceLoading);
    _search();
    await done;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Services')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _searchController,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                hintText: 'Search haircut, AC repair, doctor…',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        tooltip: 'Clear search',
                        icon: const Icon(Icons.clear),
                        onPressed: _clear,
                      )
                    : null,
              ),
              onChanged: _onChanged,
              onSubmitted: (_) => _search(),
            ),
          ),
          Expanded(
            child: BlocBuilder<ServiceBloc, ServiceState>(
              builder: (context, state) {
                if (state is ServiceLoading || state is ServiceInitial) {
                  return const LoadingIndicator(message: 'Loading services...');
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
                          _query.isEmpty ? 'No services listed yet' : 'Nothing found for "$_query"',
                          style: AppTextStyles.subtitle1,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _query.isEmpty ? 'Pull down to check again.' : 'Try a shorter or different word.',
                          style: AppTextStyles.body2,
                          textAlign: TextAlign.center,
                        ),
                        if (_query.isNotEmpty) ...[
                          const SizedBox(height: 16),
                          Center(child: OutlinedButton(onPressed: _clear, child: const Text('Show all services'))),
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
