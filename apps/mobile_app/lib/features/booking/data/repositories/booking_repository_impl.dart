import 'package:dartz/dartz.dart';
import '../../../../core/errors/exceptions.dart';
import '../../../../core/errors/failures.dart';
import '../../../../core/network/network_info.dart';
import '../../domain/entities/booking.dart';
import '../../domain/repositories/booking_repository.dart';
import '../datasources/booking_remote_datasource.dart';

class BookingRepositoryImpl implements BookingRepository {
  final BookingRemoteDataSource remoteDataSource;
  final NetworkInfo networkInfo;

  BookingRepositoryImpl({
    required this.remoteDataSource,
    required this.networkInfo,
  });

  @override
  Future<Either<Failure, Booking>> createBooking({
    required String serviceId,
    required DateTime scheduledAt,
    required String address,
    String? notes,
    String? couponCode,
    BookingDelivery delivery = BookingDelivery.atShop,
    String? idempotencyKey,
  }) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final booking = await remoteDataSource.createBooking(
        serviceId: serviceId,
        scheduledAt: scheduledAt,
        address: address,
        notes: notes,
        couponCode: couponCode,
        delivery: delivery,
        idempotencyKey: idempotencyKey,
      );
      return Right(booking);
    } on ServerException catch (e) {
      return Left(ServerFailure(message: e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, List<Booking>>> getUserBookings({
    int page = 1,
  }) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final bookings = await remoteDataSource.getUserBookings(page: page);
      return Right(bookings);
    } on ServerException catch (e) {
      return Left(ServerFailure(message: e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, Booking>> getBookingById(String id) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final booking = await remoteDataSource.getBookingById(id);
      return Right(booking);
    } on ServerException catch (e) {
      return Left(ServerFailure(message: e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, bool>> cancelBooking(String bookingId) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final result = await remoteDataSource.cancelBooking(bookingId);
      return Right(result);
    } on ServerException catch (e) {
      return Left(ServerFailure(message: e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, Booking>> rescheduleBooking(String bookingId, DateTime scheduledAt) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      return Right(await remoteDataSource.rescheduleBooking(bookingId, scheduledAt));
    } on ServerException catch (e) {
      return Left(ServerFailure(message: e.message, statusCode: e.statusCode));
    }
  }
}
