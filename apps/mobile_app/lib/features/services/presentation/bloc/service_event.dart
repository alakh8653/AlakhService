import 'package:equatable/equatable.dart';

abstract class ServiceEvent extends Equatable {
  const ServiceEvent();

  @override
  List<Object?> get props => [];
}

class LoadServices extends ServiceEvent {
  final String? category;
  final int page;

  const LoadServices({this.category, this.page = 1});

  @override
  List<Object?> get props => [category, page];
}

class SearchServices extends ServiceEvent {
  final String query;
  final String? category;

  const SearchServices({required this.query, this.category});

  @override
  List<Object?> get props => [query, category];
}

class RefreshServices extends ServiceEvent {
  const RefreshServices();
}
