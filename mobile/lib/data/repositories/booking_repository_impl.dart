import 'package:dartz/dartz.dart';

import '../../core/errors/exceptions.dart';
import '../../core/errors/failures.dart';
import '../../core/network/network_info.dart';
import '../../domain/entities/booking.dart';
import '../../domain/repositories/booking_repository.dart';
import '../datasources/remote/booking_remote_datasource.dart';

class BookingRepositoryImpl implements BookingRepository {
  const BookingRepositoryImpl({
    required this.remoteDataSource,
    required this.networkInfo,
  });

  final BookingRemoteDataSource remoteDataSource;
  final NetworkInfo networkInfo;

  @override
  Future<Either<Failure, Booking>> createBooking({
    required String serviceId,
    required String scheduledAt,
    required String address,
    String? notes,
  }) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final booking = await remoteDataSource.createBooking(
        serviceId: serviceId,
        scheduledAt: scheduledAt,
        address: address,
        notes: notes,
      );
      return Right(booking);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, List<Booking>>> getBookings({
    int page = 1,
    int limit = 20,
  }) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final bookings = await remoteDataSource.getBookings(page: page, limit: limit);
      return Right(bookings);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, Booking>> getBookingById(String id) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final booking = await remoteDataSource.getBookingById(id);
      return Right(booking);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, Booking>> cancelBooking(String id) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final booking = await remoteDataSource.cancelBooking(id);
      return Right(booking);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }
}
