import 'package:dartz/dartz.dart';

import '../entities/booking.dart';
import '../../core/errors/failures.dart';

abstract class BookingRepository {
  Future<Either<Failure, Booking>> createBooking({
    required String serviceId,
    required String scheduledAt,
    required String address,
    String? notes,
  });

  Future<Either<Failure, List<Booking>>> getBookings({
    int page = 1,
    int limit = 20,
  });

  Future<Either<Failure, Booking>> getBookingById(String id);

  Future<Either<Failure, Booking>> cancelBooking(String id);
}
