import '../../domain/entities/service.dart';

class ServiceModel extends Service {
  const ServiceModel({
    required super.id,
    required super.name,
    required super.description,
    required super.category,
    required super.priceFrom,
    required super.durationMinutes,
    super.imageUrl,
    super.rating,
    super.reviewCount,
    super.isAvailable,
  });

  factory ServiceModel.fromJson(Map<String, dynamic> json) {
    return ServiceModel(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String,
      category: json['category'] as String,
      priceFrom: (json['price_from'] as num).toDouble(),
      durationMinutes: json['duration_minutes'] as int,
      imageUrl: json['image_url'] as String?,
      rating: (json['rating'] as num?)?.toDouble(),
      reviewCount: json['review_count'] as int? ?? 0,
      isAvailable: json['is_available'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'category': category,
      'price_from': priceFrom,
      'duration_minutes': durationMinutes,
      if (imageUrl != null) 'image_url': imageUrl,
      if (rating != null) 'rating': rating,
      'review_count': reviewCount,
      'is_available': isAvailable,
    };
  }
}
