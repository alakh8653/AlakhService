import '../../domain/entities/user.dart';

class UserModel extends User {
  const UserModel({
    required super.id,
    required super.name,
    required super.phone,
    super.email,
    required super.role,
    super.avatarUrl,
    required super.isVerified,
    required super.createdAt,
  });

  /// Reads auth_service's `/auth/me` response (or a cached copy written by [toJson]).
  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String,
      name: (json['full_name'] ?? json['name'] ?? '') as String,
      phone: (json['phone'] as String?) ?? '',
      email: json['email'] as String?,
      role: (json['role'] as String?) ?? 'user',
      avatarUrl: json['avatar_url'] as String?,
      isVerified: (json['is_verified'] as bool?) ?? false,
      createdAt: DateTime.tryParse((json['created_at'] as String?) ?? '') ?? DateTime.fromMillisecondsSinceEpoch(0),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'full_name': name,
        'phone': phone,
        'email': email,
        'role': role,
        'avatar_url': avatarUrl,
        'is_verified': isVerified,
        'created_at': createdAt.toIso8601String(),
      };

  factory UserModel.fromEntity(User user) {
    return UserModel(
      id: user.id,
      name: user.name,
      phone: user.phone,
      email: user.email,
      role: user.role,
      avatarUrl: user.avatarUrl,
      isVerified: user.isVerified,
      createdAt: user.createdAt,
    );
  }
}

/// Access and refresh tokens from auth_service.
class TokenPair {
  final String accessToken;
  final String refreshToken;

  const TokenPair({required this.accessToken, required this.refreshToken});

  factory TokenPair.fromJson(Map<String, dynamic> json) => TokenPair(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String,
      );
}
