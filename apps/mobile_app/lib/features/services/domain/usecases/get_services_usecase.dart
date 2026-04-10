import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/service_entity.dart';
import '../repositories/service_repository.dart';

class GetServicesUseCase {
  final ServiceRepository repository;

  GetServicesUseCase(this.repository);

  Future<Either<Failure, List<ServiceEntity>>> call(
    GetServicesParams params,
  ) {
    return repository.getServices(
      page: params.page,
      limit: params.limit,
      category: params.category,
    );
  }
}

class GetServicesParams {
  final int page;
  final int limit;
  final String? category;

  const GetServicesParams({
    this.page = 1,
    this.limit = 20,
    this.category,
  });
}
