import '../../domain/entities/booking.dart';

class BookingModel extends Booking {
  const BookingModel({
    required super.id,
    required super.userId,
    required super.serviceId,
    required super.serviceName,
    super.providerId,
    required super.status,
    required super.scheduledAt,
    required super.address,
    required super.totalAmount,
    super.notes,
    required super.createdAt,
  });

  factory BookingModel.fromJson(Map<String, dynamic> json) {
    return BookingModel(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      serviceId: json['service_id'] as String,
      serviceName: json['service_name'] as String,
      providerId: json['provider_id'] as String?,
      status: json['status'] as String,
      scheduledAt: DateTime.parse(json['scheduled_at'] as String),
      address: json['address'] as String,
      totalAmount: (json['total_amount'] as num).toDouble(),
      notes: json['notes'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'user_id': userId,
        'service_id': serviceId,
        'service_name': serviceName,
        'provider_id': providerId,
        'status': status,
        'scheduled_at': scheduledAt.toIso8601String(),
        'address': address,
        'total_amount': totalAmount,
        'notes': notes,
        'created_at': createdAt.toIso8601String(),
      };
}
