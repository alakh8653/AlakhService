import 'package:equatable/equatable.dart';

/// Booking statuses, as booking_service's state machine names them.
class BookingStatus {
  BookingStatus._();

  static const pending = 'PENDING';
  static const confirmed = 'CONFIRMED';
  static const assigned = 'ASSIGNED';
  static const enRoute = 'PROVIDER_EN_ROUTE';
  static const inProgress = 'IN_PROGRESS';
  static const completed = 'COMPLETED';
  static const cancelled = 'CANCELLED';
  static const disputed = 'DISPUTED';
  static const refunded = 'REFUNDED';

  /// Customers may cancel until a provider is on the way.
  static const cancellable = {pending, confirmed, assigned};

  /// The provider is working on it: their live location is shared with the customer.
  static const trackable = {assigned, enRoute, inProgress};

  /// payment_service accepts payment from confirmation until completion.
  static const payable = {confirmed, assigned, enRoute, inProgress, completed};
}

class Booking extends Equatable {
  final String id;
  final String bookingNumber;
  final String userId;
  final String serviceId;
  final String serviceName;
  final String? providerId;
  final String? shopId;
  final String status;
  final DateTime scheduledAt;
  final int durationMinutes;
  final String address;
  final double totalAmount;
  final String? notes;
  final DateTime createdAt;

  const Booking({
    required this.id,
    this.bookingNumber = '',
    required this.userId,
    required this.serviceId,
    required this.serviceName,
    this.providerId,
    this.shopId,
    required this.status,
    required this.scheduledAt,
    this.durationMinutes = 0,
    required this.address,
    required this.totalAmount,
    this.notes,
    required this.createdAt,
  });

  bool get canCancel => BookingStatus.cancellable.contains(status);
  bool get canTrack => providerId != null && BookingStatus.trackable.contains(status);
  bool get canPay => BookingStatus.payable.contains(status);
  bool get canRate => status == BookingStatus.completed && shopId != null;

  @override
  List<Object?> get props => [id, userId, serviceId, status, scheduledAt, providerId];
}
