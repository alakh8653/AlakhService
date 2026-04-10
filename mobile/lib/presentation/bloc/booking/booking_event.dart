import 'package:equatable/equatable.dart';

abstract class BookingEvent extends Equatable {
  const BookingEvent();

  @override
  List<Object?> get props => [];
}

class CreateBookingRequested extends BookingEvent {
  const CreateBookingRequested({
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

class LoadBookings extends BookingEvent {}

class LoadBookingDetail extends BookingEvent {
  const LoadBookingDetail(this.bookingId);

  final String bookingId;

  @override
  List<Object> get props => [bookingId];
}

class CancelBookingRequested extends BookingEvent {
  const CancelBookingRequested(this.bookingId);

  final String bookingId;

  @override
  List<Object> get props => [bookingId];
}
