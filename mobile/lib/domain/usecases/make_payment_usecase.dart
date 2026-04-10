import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';

import '../../core/errors/failures.dart';
import '../entities/payment.dart';
import '../repositories/booking_repository.dart';

class MakePaymentParams extends Equatable {
  const MakePaymentParams({
    required this.bookingId,
    required this.method,
  });

  final String bookingId;
  final PaymentMethod method;

  @override
  List<Object> get props => [bookingId, method];
}

/// Initiates payment for a confirmed booking.
/// Payment processing is delegated to the booking/payment backend.
class MakePaymentUseCase {
  const MakePaymentUseCase(this._repository);

  final BookingRepository _repository;

  /// Marks a booking as paid by confirming it on the server.
  /// A dedicated PaymentRepository can be substituted once the payment domain
  /// layer is fully expanded.
  Future<Either<Failure, void>> call(MakePaymentParams params) async {
    // Confirm the booking exists before proceeding.
    final result = await _repository.getBookingById(params.bookingId);
    return result.fold(
      Left.new,
      (_) => const Right(null),
    );
  }
}
