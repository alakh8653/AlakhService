import 'package:equatable/equatable.dart';

class Service extends Equatable {
  const Service({
    required this.id,
    required this.name,
    required this.description,
    required this.category,
    required this.priceFrom,
    required this.durationMinutes,
    this.imageUrl,
    this.rating,
    this.reviewCount = 0,
    this.isAvailable = true,
  });

  final String id;
  final String name;
  final String description;
  final String category;
  final double priceFrom;
  final int durationMinutes;
  final String? imageUrl;
  final double? rating;
  final int reviewCount;
  final bool isAvailable;

  @override
  List<Object?> get props => [
        id, name, description, category, priceFrom,
        durationMinutes, imageUrl, rating, reviewCount, isAvailable,
      ];
}
