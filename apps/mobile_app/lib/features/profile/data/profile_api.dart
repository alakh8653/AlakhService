import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

class Profile {
  final String? fullName;
  final String? bio;

  const Profile({this.fullName, this.bio});

  factory Profile.fromJson(Map<String, dynamic> json) =>
      Profile(fullName: json['full_name'] as String?, bio: json['bio'] as String?);
}

/// The signed-in user's profile details (user_service).
class ProfileApi {
  final ApiClient apiClient;

  ProfileApi(this.apiClient);

  /// The profile, or null if the user has not saved one yet.
  Future<Profile?> get() async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.profile);
      return Profile.fromJson(response.data!);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      throw toServerException(e);
    }
  }

  Future<Profile> update({String? fullName, String? bio}) async {
    try {
      final response = await apiClient.put<Map<String, dynamic>>(
        ApiConstants.profile,
        data: {if (fullName != null) 'full_name': fullName, if (bio != null) 'bio': bio},
      );
      return Profile.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// Deletes the signed-in account for good (password required). Profile data is erased and the
  /// sign-in can't be used again; the caller should then sign out locally.
  Future<void> deleteAccount(String password) async {
    try {
      await apiClient.post<dynamic>(ApiConstants.deleteAccount, data: {'password': password});
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
