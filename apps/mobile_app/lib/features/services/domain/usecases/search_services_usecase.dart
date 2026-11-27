import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/service_entity.dart';
import '../entities/service_filters.dart';
import '../repositories/service_repository.dart';

class SearchServicesUseCase {
  final ServiceRepository repository;

  SearchServicesUseCase(this.repository);

  Future<Either<Failure, List<ServiceEntity>>> call(
    SearchServicesParams params,
  ) {
    return repository.searchServices(
      query: params.query,
      category: params.category,
      filters: params.filters,
    );
  }
}

class SearchServicesParams {
  final String query;
  final String? category;
  final ServiceFilters filters;

  const SearchServicesParams({required this.query, this.category, this.filters = ServiceFilters.none});
}
