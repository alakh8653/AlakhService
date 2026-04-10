import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/booking.dart';

abstract class BookingRepository {
  Future<Either<Failure, Booking>> createBooking({
    required String serviceId,
    required DateTime scheduledAt,
    required String address,
    String? notes,
  });

  Future<Either<Failure, List<Booking>>> getUserBookings({int page = 1});

  Future<Either<Failure, Booking>> getBookingById(String id);

  Future<Either<Failure, bool>> cancelBooking(String bookingId);
}
