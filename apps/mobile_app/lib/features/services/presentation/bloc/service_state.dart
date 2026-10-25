import 'package:equatable/equatable.dart';
import '../../domain/entities/service_entity.dart';

abstract class ServiceState extends Equatable {
  const ServiceState();

  @override
  List<Object?> get props => [];
}

class ServiceInitial extends ServiceState {
  const ServiceInitial();
}

class ServiceLoading extends ServiceState {
  const ServiceLoading();
}

class ServicesLoaded extends ServiceState {
  final List<ServiceEntity> services;
  final bool hasMore;
  final int currentPage;

  const ServicesLoaded({
    required this.services,
    this.hasMore = false,
    this.currentPage = 1,
  });

  @override
  List<Object?> get props => [services, hasMore, currentPage];
}

class ServiceError extends ServiceState {
  final String message;

  const ServiceError({required this.message});

  @override
  List<Object> get props => [message];
}

class ServiceSearchResults extends ServiceState {
  final List<ServiceEntity> results;
  final String query;

  const ServiceSearchResults({required this.results, required this.query});

  @override
  List<Object> get props => [results, query];
}
