import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
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
  const ServiceListPage({super.key});

  @override
  State<ServiceListPage> createState() => _ServiceListPageState();
}

class _ServiceListPageState extends State<ServiceListPage> {
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    context.read<ServiceBloc>().add(const LoadServices());
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
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
              decoration: InputDecoration(
                hintText: 'Search services...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          context
                              .read<ServiceBloc>()
                              .add(const LoadServices());
                        },
                      )
                    : null,
              ),
              onChanged: (q) {
                if (q.isEmpty) {
                  context.read<ServiceBloc>().add(const LoadServices());
                } else {
                  context
                      .read<ServiceBloc>()
                      .add(SearchServices(query: q));
                }
              },
            ),
          ),
          Expanded(
            child: BlocBuilder<ServiceBloc, ServiceState>(
              builder: (context, state) {
                if (state is ServiceLoading) {
                  return const LoadingIndicator(message: 'Loading services...');
                }
                if (state is ServiceError) {
                  return AppErrorWidget(
                    message: state.message,
                    onRetry: () =>
                        context.read<ServiceBloc>().add(const LoadServices()),
                  );
                }
                final services = switch (state) {
                  ServicesLoaded(:final services) => services,
                  ServiceSearchResults(:final results) => results,
                  _ => <ServiceEntity>[],
                };
                if (services.isEmpty) {
                  return Center(
                    child: Text('No services found', style: AppTextStyles.body1),
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async => context
                      .read<ServiceBloc>()
                      .add(const RefreshServices()),
                  child: ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: services.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (context, index) {
                      final service = services[index];
                      return ServiceCard(
                        service: service,
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) =>
                                ServiceDetailPage(service: service),
                          ),
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
