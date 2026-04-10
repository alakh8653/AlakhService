import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';

import '../../core/errors/failures.dart';
import '../entities/booking.dart';
import '../repositories/booking_repository.dart';

class CreateBookingParams extends Equatable {
  const CreateBookingParams({
    required this.serviceId,
    required this.scheduledAt,
    required this.address,
    this.notes,
  });

  final String serviceId;
  final String scheduledAt;
  final String address;
  final String? notes;

  @override
  List<Object?> get props => [serviceId, scheduledAt, address, notes];
}

class CreateBookingUseCase {
  const CreateBookingUseCase(this._repository);

  final BookingRepository _repository;

  Future<Either<Failure, Booking>> call(CreateBookingParams params) {
    return _repository.createBooking(
      serviceId: params.serviceId,
      scheduledAt: params.scheduledAt,
      address: params.address,
      notes: params.notes,
    );
  }
}
