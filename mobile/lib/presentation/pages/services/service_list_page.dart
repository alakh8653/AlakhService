import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../bloc/service/service_bloc.dart';
import '../../bloc/service/service_event.dart';
import '../../bloc/service/service_state.dart';
import '../../widgets/service_card.dart';
import '../../widgets/loading_indicator.dart';

class ServiceListPage extends StatefulWidget {
  const ServiceListPage({super.key});

  @override
  State<ServiceListPage> createState() => _ServiceListPageState();
}

class _ServiceListPageState extends State<ServiceListPage> {
  final _scrollController = ScrollController();
  String? _selectedCategory;

  static const _categories = [
    'All', 'Cleaning', 'Plumbing', 'Electrical', 'Painting', 'Gardening',
  ];

  @override
  void initState() {
    super.initState();
    context.read<ServiceBloc>().add(const LoadServices());
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      context.read<ServiceBloc>().add(LoadMoreServices());
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Services')),
      body: Column(
        children: [
          _buildCategoryFilter(),
          Expanded(
            child: BlocBuilder<ServiceBloc, ServiceState>(
              builder: (context, state) {
                if (state is ServiceLoading) return const LoadingIndicator();
                if (state is ServiceError) {
                  return Center(child: Text(state.message));
                }
                if (state is ServiceLoaded) {
                  if (state.services.isEmpty) {
                    return const Center(child: Text('No services found.'));
                  }
                  return RefreshIndicator(
                    onRefresh: () async =>
                        context.read<ServiceBloc>().add(RefreshServices()),
                    child: ListView.separated(
                      controller: _scrollController,
                      padding: const EdgeInsets.all(16),
                      itemCount: state.services.length +
                          (state is ServiceLoadingMore ? 1 : 0),
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        if (index == state.services.length) {
                          return const Center(
                            child: Padding(
                              padding: EdgeInsets.all(16),
                              child: CircularProgressIndicator(),
                            ),
                          );
                        }
                        return ServiceCard(service: state.services[index]);
                      },
                    ),
                  );
                }
                return const SizedBox.shrink();
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoryFilter() {
    return SizedBox(
      height: 52,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        itemCount: _categories.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final cat = _categories[index];
          final isAll = cat == 'All';
          final isSelected = isAll
              ? _selectedCategory == null
              : _selectedCategory == cat;
          return FilterChip(
            label: Text(cat),
            selected: isSelected,
            onSelected: (_) {
              setState(() => _selectedCategory = isAll ? null : cat);
              context.read<ServiceBloc>().add(
                    FilterByCategory(isAll ? null : cat),
                  );
            },
          );
        },
      ),
    );
  }
}
