import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/service_entity.dart';
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
    );
  }
}

class SearchServicesParams {
  final String query;
  final String? category;

  const SearchServicesParams({required this.query, this.category});
}
