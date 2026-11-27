import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/service_entity.dart';
import '../entities/service_filters.dart';

abstract class ServiceRepository {
  Future<Either<Failure, List<ServiceEntity>>> getServices({
    int page = 1,
    int limit = 20,
    String? category,
    ServiceFilters filters = ServiceFilters.none,
  });

  Future<Either<Failure, List<ServiceEntity>>> searchServices({
    required String query,
    String? category,
    ServiceFilters filters = ServiceFilters.none,
  });

  Future<Either<Failure, ServiceEntity>> getServiceById(String id);
}
