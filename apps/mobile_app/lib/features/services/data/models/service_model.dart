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
  });

  factory ServiceModel.fromJson(Map<String, dynamic> json) {
    return ServiceModel(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String,
      category: json['category'] as String,
      basePrice: (json['base_price'] as num).toDouble(),
      priceUnit: json['price_unit'] as String,
      rating: (json['rating'] as num?)?.toDouble() ?? 0.0,
      reviewCount: json['review_count'] as int? ?? 0,
      imageUrl: json['image_url'] as String?,
      isAvailable: json['is_available'] as bool? ?? true,
      tags: (json['tags'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'description': description,
        'category': category,
        'base_price': basePrice,
        'price_unit': priceUnit,
        'rating': rating,
        'review_count': reviewCount,
        'image_url': imageUrl,
        'is_available': isAvailable,
        'tags': tags,
      };
}
