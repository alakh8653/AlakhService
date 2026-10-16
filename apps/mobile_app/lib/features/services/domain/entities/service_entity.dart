import 'package:equatable/equatable.dart';

/// How a service is delivered: the customer visits the shop, a provider visits the customer, or the
/// item (car, bike, laptop, phone, AC...) is collected from the customer and brought back.
class ServiceMode {
  ServiceMode._();

  static const atShop = 'AT_SHOP';
  static const atHome = 'AT_HOME';
  static const pickupDrop = 'PICKUP_DROP';

  /// Modes that need the customer's address.
  static const needsAddress = {atHome, pickupDrop};
}

class ServiceEntity extends Equatable {
  final String id;
  final String name;
  final String description;
  final String category;
  final double basePrice;
  final String priceUnit;
  final double rating;
  final int reviewCount;
  final String? imageUrl;
  final bool isAvailable;
  final List<String> tags;
  final String? shopId;
  final int? durationMinutes;

  /// The ways this service can be delivered (ServiceMode values), in the shop's order.
  final List<String> serviceModes;

  /// Added to the price for a home visit / for pickup & drop, in rupees.
  final double homeVisitFee;
  final double pickupFee;

  const ServiceEntity({
    required this.id,
    required this.name,
    required this.description,
    required this.category,
    required this.basePrice,
    required this.priceUnit,
    this.rating = 0.0,
    this.reviewCount = 0,
    this.imageUrl,
    this.isAvailable = true,
    this.tags = const [],
    this.shopId,
    this.durationMinutes,
    this.serviceModes = const [ServiceMode.atShop],
    this.homeVisitFee = 0,
    this.pickupFee = 0,
  });

  /// The extra charge for delivering it in [mode].
  double feeFor(String mode) => switch (mode) {
        ServiceMode.atHome => homeVisitFee,
        ServiceMode.pickupDrop => pickupFee,
        _ => 0,
      };

  @override
  List<Object?> get props => [id, name, category, basePrice, isAvailable];
}
