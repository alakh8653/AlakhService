import '../../domain/entities/booking.dart';

/// The app keeps the service address in the booking's notes, on a line of its own.
const _addressPrefix = 'Address: ';

class BookingModel extends Booking {
  const BookingModel({
    required super.id,
    super.bookingNumber,
    required super.userId,
    required super.serviceId,
    required super.serviceName,
    super.providerId,
    super.shopId,
    required super.status,
    required super.scheduledAt,
    super.durationMinutes,
    required super.address,
    required super.totalAmount,
    super.listPrice,
    super.couponCode,
    super.notes,
    required super.createdAt,
  });

  /// Reads booking_service's response. Amounts arrive in paise.
  factory BookingModel.fromJson(Map<String, dynamic> json, {String? serviceName}) {
    final rawNotes = json['notes'] as String?;
    final lines = (rawNotes ?? '').split('\n');
    final addressLine = lines.firstWhere((l) => l.startsWith(_addressPrefix), orElse: () => '');
    final otherNotes = lines.where((l) => !l.startsWith(_addressPrefix)).join('\n').trim();
    return BookingModel(
      id: json['id'] as String,
      bookingNumber: (json['booking_number'] as String?) ?? '',
      userId: json['customer_id'] as String,
      serviceId: json['service_id'] as String,
      serviceName: serviceName ?? 'Service',
      providerId: json['provider_id'] as String?,
      shopId: json['shop_id'] as String?,
      status: json['status'] as String,
      scheduledAt: DateTime.parse(json['scheduled_at'] as String).toLocal(),
      durationMinutes: (json['duration_minutes'] as int?) ?? 0,
      address: addressLine.replaceFirst(_addressPrefix, ''),
      totalAmount: ((json['total_amount'] as num?) ?? 0) / 100,
      listPrice: json['list_price'] == null ? null : (json['list_price'] as num) / 100,
      couponCode: json['coupon_code'] as String?,
      notes: otherNotes.isEmpty ? null : otherNotes,
      createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
    );
  }

  /// Notes as sent to booking_service: the address line, then anything the customer wrote.
  static String composeNotes(String address, String? notes) =>
      [if (address.trim().isNotEmpty) '$_addressPrefix${address.trim()}', if (notes != null && notes.trim().isNotEmpty) notes.trim()]
          .join('\n');
}
