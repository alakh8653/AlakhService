import 'package:equatable/equatable.dart';

class Booking extends Equatable {
  final String id;
  final String userId;
  final String serviceId;
  final String serviceName;
  final String? providerId;
  final String status;
  final DateTime scheduledAt;
  final String address;
  final double totalAmount;
  final String? notes;
  final DateTime createdAt;

  const Booking({
    required this.id,
    required this.userId,
    required this.serviceId,
    required this.serviceName,
    this.providerId,
    required this.status,
    required this.scheduledAt,
    required this.address,
    required this.totalAmount,
    this.notes,
    required this.createdAt,
  });

  @override
  List<Object?> get props => [id, userId, serviceId, status, scheduledAt];
}
