import 'package:equatable/equatable.dart';

enum BookingStatus { pending, confirmed, inProgress, completed, cancelled }

class Booking extends Equatable {
  const Booking({
    required this.id,
    required this.serviceId,
    required this.serviceName,
    required this.userId,
    required this.status,
    required this.scheduledAt,
    required this.address,
    required this.totalAmount,
    this.notes,
    this.providerId,
    this.providerName,
    this.createdAt,
  });

  final String id;
  final String serviceId;
  final String serviceName;
  final String userId;
  final BookingStatus status;
  final DateTime scheduledAt;
  final String address;
  final double totalAmount;
  final String? notes;
  final String? providerId;
  final String? providerName;
  final DateTime? createdAt;

  bool get isActive =>
      status == BookingStatus.pending || status == BookingStatus.confirmed;

  bool get isCancellable => isActive;

  @override
  List<Object?> get props => [
        id, serviceId, serviceName, userId, status,
        scheduledAt, address, totalAmount, notes,
        providerId, providerName, createdAt,
      ];
}
