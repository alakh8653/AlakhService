import '../../domain/entities/booking.dart';

class BookingModel extends Booking {
  const BookingModel({
    required super.id,
    required super.serviceId,
    required super.serviceName,
    required super.userId,
    required super.status,
    required super.scheduledAt,
    required super.address,
    required super.totalAmount,
    super.notes,
    super.providerId,
    super.providerName,
    super.createdAt,
  });

  factory BookingModel.fromJson(Map<String, dynamic> json) {
    return BookingModel(
      id: json['id'] as String,
      serviceId: json['service_id'] as String,
      serviceName: json['service_name'] as String,
      userId: json['user_id'] as String,
      status: BookingStatus.values.firstWhere(
        (s) => s.name == (json['status'] as String).toLowerCase(),
        orElse: () => BookingStatus.pending,
      ),
      scheduledAt: DateTime.parse(json['scheduled_at'] as String),
      address: json['address'] as String,
      totalAmount: (json['total_amount'] as num).toDouble(),
      notes: json['notes'] as String?,
      providerId: json['provider_id'] as String?,
      providerName: json['provider_name'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'service_id': serviceId,
      'service_name': serviceName,
      'user_id': userId,
      'status': status.name,
      'scheduled_at': scheduledAt.toIso8601String(),
      'address': address,
      'total_amount': totalAmount,
      if (notes != null) 'notes': notes,
      if (providerId != null) 'provider_id': providerId,
      if (providerName != null) 'provider_name': providerName,
      if (createdAt != null) 'created_at': createdAt!.toIso8601String(),
    };
  }
}
