import 'package:equatable/equatable.dart';

import '../../../domain/entities/service.dart';

sealed class ServiceState extends Equatable {
  const ServiceState();

  @override
  List<Object?> get props => [];
}

class ServiceInitial extends ServiceState {}

class ServiceLoading extends ServiceState {}

class ServiceLoaded extends ServiceState {
  const ServiceLoaded({
    required this.services,
    this.selectedCategory,
    this.hasMore = false,
  });

  final List<Service> services;
  final String? selectedCategory;
  final bool hasMore;

  ServiceLoaded copyWith({
    List<Service>? services,
    String? selectedCategory,
    bool? hasMore,
  }) {
    return ServiceLoaded(
      services: services ?? this.services,
      selectedCategory: selectedCategory ?? this.selectedCategory,
      hasMore: hasMore ?? this.hasMore,
    );
  }

  @override
  List<Object?> get props => [services, selectedCategory, hasMore];
}

class ServiceDetailLoaded extends ServiceState {
  const ServiceDetailLoaded(this.service);

  final Service service;

  @override
  List<Object> get props => [service];
}

class ServiceError extends ServiceState {
  const ServiceError(this.message);

  final String message;

  @override
  List<Object> get props => [message];
}

class ServiceLoadingMore extends ServiceLoaded {
  const ServiceLoadingMore({
    required super.services,
    super.selectedCategory,
  });
}
