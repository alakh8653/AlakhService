import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';

import '../../core/errors/failures.dart';
import '../entities/service.dart';
import '../repositories/service_repository.dart';

class GetServicesParams extends Equatable {
  const GetServicesParams({this.page = 1, this.limit = 20, this.category});

  final int page;
  final int limit;
  final String? category;

  @override
  List<Object?> get props => [page, limit, category];
}

class GetServicesUseCase {
  const GetServicesUseCase(this._repository);

  final ServiceRepository _repository;

  Future<Either<Failure, List<Service>>> call(GetServicesParams params) {
    return _repository.getServices(
      page: params.page,
      limit: params.limit,
      category: params.category,
    );
  }
}
