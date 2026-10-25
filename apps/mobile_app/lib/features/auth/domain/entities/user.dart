import 'package:equatable/equatable.dart';

class User extends Equatable {
  final String id;
  final String name;
  final String phone;
  final String? email;
  final String role;
  final String? avatarUrl;
  final bool isVerified;
  final DateTime createdAt;

  const User({
    required this.id,
    required this.name,
    required this.phone,
    this.email,
    required this.role,
    this.avatarUrl,
    required this.isVerified,
    required this.createdAt,
  });

  @override
  List<Object?> get props => [id, name, phone, email, role, isVerified];
}
