import 'package:equatable/equatable.dart';

class User extends Equatable {
  const User({
    required this.id,
    required this.name,
    required this.email,
    required this.phone,
    this.avatarUrl,
    this.isVerified = false,
    this.createdAt,
  });

  final String id;
  final String name;
  final String email;
  final String phone;
  final String? avatarUrl;
  final bool isVerified;
  final DateTime? createdAt;

  @override
  List<Object?> get props => [id, name, email, phone, avatarUrl, isVerified, createdAt];
}
