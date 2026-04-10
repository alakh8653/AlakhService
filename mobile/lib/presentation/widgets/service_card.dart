import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../domain/entities/service.dart';
import '../../../config/routes.dart';
import '../../../core/utils/helpers.dart';

class ServiceCard extends StatelessWidget {
  const ServiceCard({super.key, required this.service});
  final Service service;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => context.push('/services/${service.id}'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(width: 72, height: 72, decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, borderRadius: BorderRadius.circular(12)),
                child: service.imageUrl != null ? ClipRRect(borderRadius: BorderRadius.circular(12), child: Image.network(service.imageUrl!, fit: BoxFit.cover)) : Icon(Icons.home_repair_service, color: Theme.of(context).colorScheme.primary, size: 36)),
              const SizedBox(width: 16),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(service.name, style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(service.category, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey)),
                const SizedBox(height: 4),
                Row(children: [
                  if (service.rating != null) ...[const Icon(Icons.star, size: 14, color: Colors.amber), const SizedBox(width: 2), Text('${service.rating!.toStringAsFixed(1)} ', style: const TextStyle(fontSize: 12))],
                  Text('From ${AppHelpers.formatCurrency(service.priceFrom * 100)}', style: TextStyle(color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.w600, fontSize: 13)),
                ]),
              ])),
            ],
          ),
        ),
      ),
    );
  }
}
