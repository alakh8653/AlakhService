import 'package:equatable/equatable.dart';

import '../../domain/entities/service_filters.dart';

abstract class ServiceEvent extends Equatable {
  const ServiceEvent();

  @override
  List<Object?> get props => [];
}

class LoadServices extends ServiceEvent {
  final String? category;
  final int page;
  final ServiceFilters filters;

  const LoadServices({this.category, this.page = 1, this.filters = ServiceFilters.none});

  @override
  List<Object?> get props => [category, page, filters];
}

class SearchServices extends ServiceEvent {
  final String query;
  final String? category;
  final ServiceFilters filters;

  const SearchServices({required this.query, this.category, this.filters = ServiceFilters.none});

  @override
  List<Object?> get props => [query, category, filters];
}

class RefreshServices extends ServiceEvent {
  const RefreshServices();
}
