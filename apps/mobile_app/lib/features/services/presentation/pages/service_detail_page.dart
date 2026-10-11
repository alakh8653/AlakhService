import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_state.dart';
import '../../../booking/presentation/bloc/booking_bloc.dart';
import '../../../booking/presentation/pages/booking_page.dart';
import '../../../queue/data/queue_api.dart';
import '../../../queue/presentation/pages/queue_status_page.dart';
import '../../domain/entities/service_entity.dart';

class ServiceDetailPage extends StatefulWidget {
  final ServiceEntity service;

  const ServiceDetailPage({super.key, required this.service});

  @override
  State<ServiceDetailPage> createState() => _ServiceDetailPageState();
}

class _ServiceDetailPageState extends State<ServiceDetailPage> {
  String? _openQueueId;
  bool _joining = false;

  ServiceEntity get service => widget.service;

  @override
  void initState() {
    super.initState();
    // Walk-in queue, if the shop runs one for this service.
    sl<QueueApi>().openQueueFor(service.id).then((id) {
      if (mounted) setState(() => _openQueueId = id);
    }).catchError((_) {});
  }

  void _book() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => BlocProvider<BookingBloc>(
          create: (_) => sl<BookingBloc>(),
          child: BookingPage(serviceId: service.id, serviceName: service.name, servicePrice: service.basePrice),
        ),
      ),
    );
  }

  Future<void> _joinQueue() async {
    final auth = context.read<AuthBloc>().state;
    final queueId = _openQueueId;
    if (auth is! Authenticated || queueId == null) return;
    setState(() => _joining = true);
    try {
      final ticket = await sl<QueueApi>().join(queueId: queueId, serviceId: service.id, customerId: auth.user.id);
      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => QueueStatusPage(ticket: ticket, customerId: auth.user.id, serviceName: service.name),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 240,
            pinned: true,
            flexibleSpace: FlexibleSpaceBar(
              title: Text(service.name),
              background: service.imageUrl != null
                  ? Image.network(service.imageUrl!, fit: BoxFit.cover)
                  : Container(
                      color: AppColors.primaryLight,
                      child: const Icon(Icons.home_repair_service, size: 80, color: AppColors.primary),
                    ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(service.name, style: AppTextStyles.heading2),
                  if (service.durationMinutes != null) ...[
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        const Icon(Icons.schedule, size: 16, color: AppColors.textSecondary),
                        const SizedBox(width: 4),
                        Text('About ${service.durationMinutes} minutes', style: AppTextStyles.caption),
                      ],
                    ),
                  ],
                  const SizedBox(height: 16),
                  const Text('About this service', style: AppTextStyles.subtitle1),
                  const SizedBox(height: 8),
                  Text(
                    service.description.isEmpty ? 'No description yet.' : service.description,
                    style: AppTextStyles.body2,
                  ),
                  if (service.tags.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      children: service.tags
                          .map((t) => Chip(label: Text(t, style: AppTextStyles.caption), backgroundColor: AppColors.primaryLight))
                          .toList(),
                    ),
                  ],
                  const SizedBox(height: 24),
                  Row(
                    children: [
                      const Text('Price', style: AppTextStyles.body2),
                      const SizedBox(width: 8),
                      Text(
                        '₹${service.basePrice.toStringAsFixed(service.basePrice % 1 == 0 ? 0 : 2)}',
                        style: AppTextStyles.heading3.copyWith(color: AppColors.primary),
                      ),
                      Text(' / ${service.priceUnit}', style: AppTextStyles.body2),
                    ],
                  ),
                  const SizedBox(height: 32),
                  CustomButton(label: 'Book Now', onPressed: service.isAvailable ? _book : null),
                  if (_openQueueId != null) ...[
                    const SizedBox(height: 12),
                    CustomButton(
                      label: 'Join the walk-in queue',
                      variant: ButtonVariant.outlined,
                      isLoading: _joining,
                      onPressed: _joining ? null : _joinQueue,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
