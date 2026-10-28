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

  /// Identifies the booking attempt: the page keeps it while the customer retries the same booking.
  final String? idempotencyKey;

  /// Spend the customer's loyalty points on it.
  final bool usePoints;

  const CreateBookingRequested({
    required this.serviceId,
    required this.scheduledAt,
    required this.address,
    this.notes,
    this.couponCode,
    this.delivery = BookingDelivery.atShop,
    this.idempotencyKey,
    this.usePoints = false,
  });

  @override
  List<Object?> get props => [serviceId, scheduledAt, address, notes, couponCode, delivery, idempotencyKey, usePoints];
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
