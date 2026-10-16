import 'package:equatable/equatable.dart';

import '../../domain/entities/booking.dart';

abstract class BookingEvent extends Equatable {
  const BookingEvent();

  @override
  List<Object?> get props => [];
}

class CreateBookingRequested extends BookingEvent {
  final String serviceId;
  final DateTime scheduledAt;
  final String address;
  final String? notes;
  final String? couponCode;
  final BookingDelivery delivery;

  const CreateBookingRequested({
    required this.serviceId,
    required this.scheduledAt,
    required this.address,
    this.notes,
    this.couponCode,
    this.delivery = BookingDelivery.atShop,
  });

  @override
  List<Object?> get props => [serviceId, scheduledAt, address, delivery];
}

class LoadUserBookings extends BookingEvent {
  final int page;

  const LoadUserBookings({this.page = 1});

  @override
  List<Object> get props => [page];
}

class CancelBookingRequested extends BookingEvent {
  final String bookingId;

  const CancelBookingRequested(this.bookingId);

  @override
  List<Object> get props => [bookingId];
}

class RefreshBookings extends BookingEvent {
  const RefreshBookings();
}
