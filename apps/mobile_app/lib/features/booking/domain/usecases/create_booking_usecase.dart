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
      delivery: params.delivery,
      idempotencyKey: params.idempotencyKey,
      usePoints: params.usePoints,
    );
  }
}

class CreateBookingParams {
  final String serviceId;
  final DateTime scheduledAt;
  final String address;
  final String? notes;
  final String? couponCode;
  final BookingDelivery delivery;

  /// The same for every try of one booking, so a retry never books twice.
  final String? idempotencyKey;
  final bool usePoints;

  const CreateBookingParams({
    required this.serviceId,
    required this.scheduledAt,
    required this.address,
    this.notes,
    this.couponCode,
    this.delivery = BookingDelivery.atShop,
    this.idempotencyKey,
    this.usePoints = false,
  });
}
