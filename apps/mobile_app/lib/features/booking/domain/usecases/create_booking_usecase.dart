import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/booking.dart';
import '../repositories/booking_repository.dart';

class CreateBookingUseCase {
  final BookingRepository repository;

  CreateBookingUseCase(this.repository);

  Future<Either<Failure, Booking>> call(CreateBookingParams params) {
    return repository.createBooking(
      serviceId: params.serviceId,
      scheduledAt: params.scheduledAt,
      address: params.address,
      notes: params.notes,
      couponCode: params.couponCode,
    );
  }
}

class CreateBookingParams {
  final String serviceId;
  final DateTime scheduledAt;
  final String address;
  final String? notes;
  final String? couponCode;

  const CreateBookingParams({
    required this.serviceId,
    required this.scheduledAt,
    required this.address,
    this.notes,
    this.couponCode,
  });
}
