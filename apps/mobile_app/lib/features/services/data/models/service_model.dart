import '../../domain/entities/service_entity.dart';

class ServiceModel extends ServiceEntity {
  const ServiceModel({
    required super.id,
    required super.name,
    required super.description,
    required super.category,
    required super.basePrice,
    required super.priceUnit,
    super.rating,
    super.reviewCount,
    super.imageUrl,
    super.isAvailable,
    super.tags,
    super.shopId,
    super.durationMinutes,
    super.serviceModes,
    super.homeVisitFee,
    super.pickupFee,
    super.shopVerified,
    super.distanceKm,
  });

  /// This listing with its shop's rating (reviews are of the shop that does the work).
  ServiceModel withRating(double rating, int reviewCount, {bool? verified}) => ServiceModel(
        id: id,
        name: name,
        description: description,
        category: category,
        basePrice: basePrice,
        priceUnit: priceUnit,
        rating: rating,
        reviewCount: reviewCount,
        imageUrl: imageUrl,
        isAvailable: isAvailable,
        tags: tags,
        shopId: shopId,
        durationMinutes: durationMinutes,
        serviceModes: serviceModes,
        homeVisitFee: homeVisitFee,
        pickupFee: pickupFee,
        shopVerified: verified ?? shopVerified,
        distanceKm: distanceKm,
      );

  /// Reads a service_catalog listing. Prices arrive in paise (`price_cents`).
  factory ServiceModel.fromJson(Map<String, dynamic> json) {
    final duration = json['duration_minutes'] as int?;
    final ratedBy = (json['shop_rating_count'] as num?)?.toInt() ?? 0;
    final rawTags = json['tags'];
    final tags = rawTags is List
        ? rawTags.map((e) => e.toString()).toList()
        : rawTags is String && rawTags.isNotEmpty
            ? rawTags.split(',').map((t) => t.trim()).where((t) => t.isNotEmpty).toList()
            : <String>[];
    return ServiceModel(
      id: json['id'] as String,
      name: json['name'] as String,
      description: (json['description'] as String?) ?? '',
      category: (json['category'] as String?) ?? 'Service',
      basePrice: ((json['price_cents'] as num?) ?? 0) / 100,
      priceUnit: duration != null ? '$duration min' : 'visit',
      isAvailable: (json['is_active'] as bool?) ?? true,
      // The shop's rating, when the catalogue sends it (the ratings lookup may refine it).
      rating: ratedBy > 0 ? ((json['shop_rating'] as num?) ?? 0).toDouble() : 0,
      reviewCount: ratedBy,
      distanceKm: (json['distance_km'] as num?)?.toDouble(),
      tags: tags,
      shopId: json['shop_id'] as String?,
      durationMinutes: duration,
      // Listings from before delivery modes are at the shop only.
      serviceModes: (json['service_modes'] as List?)?.map((m) => m.toString()).toList() ?? const [ServiceMode.atShop],
      homeVisitFee: ((json['home_visit_fee_cents'] as num?) ?? 0) / 100,
      pickupFee: ((json['pickup_fee_cents'] as num?) ?? 0) / 100,
      // From listings that carry their shop's badge (or its embedded shop).
      shopVerified: json['shop_is_verified'] == true ||
          (json['shop'] is Map && (json['shop'] as Map)['is_verified'] == true),
    );
  }
}
