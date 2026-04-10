import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../repositories/booking_repository.dart';

class CancelBookingUseCase {
  final BookingRepository repository;

  CancelBookingUseCase(this.repository);

  Future<Either<Failure, bool>> call(String bookingId) {
    return repository.cancelBooking(bookingId);
  }
}
