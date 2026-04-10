import 'package:equatable/equatable.dart';

import '../../../domain/entities/booking.dart';

sealed class BookingState extends Equatable {
  const BookingState();

  @override
  List<Object?> get props => [];
}

class BookingInitial extends BookingState {}

class BookingLoading extends BookingState {}

class BookingCreated extends BookingState {
  const BookingCreated(this.booking);

  final Booking booking;

  @override
  List<Object> get props => [booking];
}

class BookingsLoaded extends BookingState {
  const BookingsLoaded(this.bookings);

  final List<Booking> bookings;

  @override
  List<Object> get props => [bookings];
}

class BookingDetailLoaded extends BookingState {
  const BookingDetailLoaded(this.booking);

  final Booking booking;

  @override
  List<Object> get props => [booking];
}

class BookingCancelled extends BookingState {
  const BookingCancelled(this.booking);

  final Booking booking;

  @override
  List<Object> get props => [booking];
}

class BookingError extends BookingState {
  const BookingError(this.message);

  final String message;

  @override
  List<Object> get props => [message];
}
