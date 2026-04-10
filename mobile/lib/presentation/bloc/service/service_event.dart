import 'package:equatable/equatable.dart';

abstract class ServiceEvent extends Equatable {
  const ServiceEvent();

  @override
  List<Object?> get props => [];
}

class LoadServices extends ServiceEvent {
  const LoadServices({this.category, this.page = 1});

  final String? category;
  final int page;

  @override
  List<Object?> get props => [category, page];
}

class LoadMoreServices extends ServiceEvent {}

class RefreshServices extends ServiceEvent {}

class LoadServiceDetail extends ServiceEvent {
  const LoadServiceDetail(this.serviceId);

  final String serviceId;

  @override
  List<Object> get props => [serviceId];
}

class FilterByCategory extends ServiceEvent {
  const FilterByCategory(this.category);

  final String? category;

  @override
  List<Object?> get props => [category];
}
