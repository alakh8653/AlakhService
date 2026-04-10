import 'package:dartz/dartz.dart';

import '../entities/service.dart';
import '../../core/errors/failures.dart';

abstract class ServiceRepository {
  Future<Either<Failure, List<Service>>> getServices({
    int page = 1,
    int limit = 20,
    String? category,
  });

  Future<Either<Failure, Service>> getServiceById(String id);

  Future<Either<Failure, List<String>>> getCategories();
}
