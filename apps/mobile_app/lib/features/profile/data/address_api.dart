import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

class SavedAddress {
  final String id;
  final String label;
  final String street;
  final String city;
  final String state;
  final String postalCode;
  final bool isDefault;

  /// Map position, when the address was saved with one.
  final double? latitude;
  final double? longitude;

  const SavedAddress({
    required this.id,
    required this.label,
    required this.street,
    required this.city,
    required this.state,
    required this.postalCode,
    required this.isDefault,
    this.latitude,
    this.longitude,
  });

  /// One line, as written into a booking.
  String get oneLine => [street, city, '$state $postalCode'.trim()].where((p) => p.trim().isNotEmpty).join(', ');

  factory SavedAddress.fromJson(Map<String, dynamic> json) => SavedAddress(
        id: json['id'] as String,
        label: json['label'] as String,
        street: json['street'] as String,
        city: json['city'] as String,
        state: (json['state'] as String?) ?? '',
        postalCode: (json['postal_code'] as String?) ?? '',
        isDefault: (json['is_default'] as bool?) ?? false,
        latitude: (json['latitude'] as num?)?.toDouble(),
        longitude: (json['longitude'] as num?)?.toDouble(),
      );
}

/// The signed-in customer's saved addresses (user_service).
class AddressApi {
  final ApiClient apiClient;

  AddressApi(this.apiClient);

  Future<T> _call<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// Saved addresses, the default one first.
  Future<List<SavedAddress>> list() => _call(() async {
        final response = await apiClient.get<List<dynamic>>(ApiConstants.addresses);
        final all = (response.data ?? []).map((e) => SavedAddress.fromJson(e as Map<String, dynamic>)).toList();
        all.sort((a, b) => (b.isDefault ? 1 : 0) - (a.isDefault ? 1 : 0));
        return all;
      });

  Future<SavedAddress> add({
    required String label,
    required String street,
    required String city,
    required String state,
    required String postalCode,
  }) =>
      _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(ApiConstants.addresses, data: {
          'label': label,
          'street': street,
          'city': city,
          'state': state,
          'postal_code': postalCode,
          'country': 'India',
        });
        return SavedAddress.fromJson(response.data!);
      });

  Future<void> delete(String id) => _call(() => apiClient.delete<dynamic>(ApiConstants.address(id)));

  Future<void> makeDefault(String id) => _call(() => apiClient.post<dynamic>(ApiConstants.defaultAddress(id)));
}
