import 'package:dartz/dartz.dart';

import '../../core/errors/exceptions.dart';
import '../../core/errors/failures.dart';
import '../../core/network/network_info.dart';
import '../../domain/entities/service.dart';
import '../../domain/repositories/service_repository.dart';
import '../datasources/remote/service_remote_datasource.dart';

class ServiceRepositoryImpl implements ServiceRepository {
  const ServiceRepositoryImpl({
    required this.remoteDataSource,
    required this.networkInfo,
  });

  final ServiceRemoteDataSource remoteDataSource;
  final NetworkInfo networkInfo;

  @override
  Future<Either<Failure, List<Service>>> getServices({
    int page = 1,
    int limit = 20,
    String? category,
  }) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final services = await remoteDataSource.getServices(
        page: page,
        limit: limit,
        category: category,
      );
      return Right(services);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, Service>> getServiceById(String id) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final service = await remoteDataSource.getServiceById(id);
      return Right(service);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, List<String>>> getCategories() async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final categories = await remoteDataSource.getCategories();
      return Right(categories);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }
}
