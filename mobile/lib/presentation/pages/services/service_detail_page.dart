import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../bloc/service/service_bloc.dart';
import '../../bloc/service/service_event.dart';
import '../../bloc/service/service_state.dart';
import '../../../config/routes.dart';
import '../../../core/utils/helpers.dart';
import '../../../domain/entities/service.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/loading_indicator.dart';

class ServiceDetailPage extends StatefulWidget {
  const ServiceDetailPage({super.key, required this.serviceId});

  final String serviceId;

  @override
  State<ServiceDetailPage> createState() => _ServiceDetailPageState();
}

class _ServiceDetailPageState extends State<ServiceDetailPage> {
  @override
  void initState() {
    super.initState();
    context.read<ServiceBloc>().add(LoadServiceDetail(widget.serviceId));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Service Detail')),
      body: BlocBuilder<ServiceBloc, ServiceState>(
        builder: (context, state) {
          if (state is ServiceLoading) return const LoadingIndicator();
          if (state is ServiceError) {
            return Center(child: Text(state.message));
          }
          if (state is ServiceDetailLoaded) {
            return _ServiceDetailBody(service: state.service);
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

class _ServiceDetailBody extends StatelessWidget {
  const _ServiceDetailBody({required this.service});

  final Service service;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  height: 220,
                  width: double.infinity,
                  color: Theme.of(context).colorScheme.primaryContainer,
                  child: service.imageUrl != null
                      ? Image.network(service.imageUrl!, fit: BoxFit.cover)
                      : Icon(
                          Icons.home_repair_service,
                          size: 80,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                ),
                Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              service.name,
                              style: Theme.of(context).textTheme.headlineMedium,
                            ),
                          ),
                          if (service.rating != null)
                            Row(
                              children: [
                                const Icon(Icons.star, color: Colors.amber, size: 20),
                                const SizedBox(width: 4),
                                Text(
                                  service.rating!.toStringAsFixed(1),
                                  style: Theme.of(context).textTheme.labelLarge,
                                ),
                                Text(
                                  ' (${service.reviewCount})',
                                  style: Theme.of(context)
                                      .textTheme
                                      .bodySmall
                                      ?.copyWith(color: Colors.grey),
                                ),
                              ],
                            ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          const Icon(Icons.access_time, size: 16, color: Colors.grey),
                          const SizedBox(width: 4),
                          Text(
                            '${service.durationMinutes} min',
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
                                ?.copyWith(color: Colors.grey),
                          ),
                          const SizedBox(width: 16),
                          Text(
                            AppHelpers.formatCurrency(service.priceFrom * 100),
                            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                  color: Theme.of(context).colorScheme.primary,
                                ),
                          ),
                          const Text(' / visit'),
                        ],
                      ),
                      const SizedBox(height: 20),
                      Text(
                        'About this service',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        service.description,
                        style: Theme.of(context)
                            .textTheme
                            .bodyLarge
                            ?.copyWith(color: Colors.grey.shade700),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(20),
          child: CustomButton(
            label: 'Book Now',
            onPressed: () => context.push(
              '${Routes.booking}?serviceId=${service.id}',
            ),
          ),
        ),
      ],
    );
  }
}
