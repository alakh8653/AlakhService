import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// Someone on a shop's team, as customers see them (shop_service): to ask for when booking.
class TeamMember {
  final String id;
  final String name;
  final String role;

  /// The services they do; empty means all of the shop's.
  final List<String> serviceIds;

  const TeamMember({required this.id, required this.name, required this.role, this.serviceIds = const []});

  bool does(String serviceId) => serviceIds.isEmpty || serviceIds.contains(serviceId);

  factory TeamMember.fromJson(Map<String, dynamic> json) => TeamMember(
        id: json['id'] as String,
        name: json['name'] as String,
        role: (json['role'] as String?) ?? '',
        serviceIds: [for (final s in (json['service_ids'] as List? ?? const [])) s.toString()],
      );
}

class TeamApi {
  final ApiClient apiClient;

  TeamApi(this.apiClient);

  Future<List<TeamMember>> forShop(String shopId) async {
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.shopTeam(shopId));
      return [for (final m in response.data ?? const []) TeamMember.fromJson(m as Map<String, dynamic>)];
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
