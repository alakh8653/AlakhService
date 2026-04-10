import 'package:equatable/equatable.dart';

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
  });

  @override
  List<Object?> get props => [id, name, category, basePrice, isAvailable];
}
