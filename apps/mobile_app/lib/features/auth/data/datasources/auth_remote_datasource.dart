import 'package:dio/dio.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../shared/utils/phone.dart';
import '../models/user_model.dart';

/// Calls auth_service through the gateway. Every failure is a ServerException with a readable message.
abstract class AuthRemoteDataSource {
  /// Signs in with an email or phone number and password.
  Future<TokenPair> login({required String identifier, required String password});

  Future<void> register({required String name, required String phone, required String password});

  /// Sends a one-time code by SMS or email for 'registration', 'login' or 'password_reset'.
  Future<void> sendCode({required String identifier, required String purpose});

  /// Verifies a code. 'registration' and 'login' sign in; 'password_reset' returns a reset token.
  Future<Map<String, dynamic>> verifyCode({required String identifier, required String code, required String purpose});

  Future<void> resetPassword({required String resetToken, required String newPassword});

  Future<UserModel> currentUser();

  Future<void> logout(String refreshToken);
}

class AuthRemoteDataSourceImpl implements AuthRemoteDataSource {
  final ApiClient apiClient;

  AuthRemoteDataSourceImpl({required this.apiClient});

  Future<T> _call<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  @override
  Future<TokenPair> login({required String identifier, required String password}) => _call(() async {
        final id = normalizeIdentifier(identifier);
        final response = await apiClient.post<Map<String, dynamic>>(
          ApiConstants.login,
          data: {id.contains('@') ? 'email' : 'phone': id, 'password': password},
          options: ApiClient.anonymous,
        );
        return TokenPair.fromJson(response.data!);
      });

  @override
  Future<void> register({required String name, required String phone, required String password}) => _call(() async {
        await apiClient.post<dynamic>(
          ApiConstants.register,
          data: {'full_name': name.trim(), 'phone': normalizePhone(phone), 'password': password},
          options: ApiClient.anonymous,
        );
      });

  @override
  Future<void> sendCode({required String identifier, required String purpose}) => _call(() async {
        await apiClient.post<dynamic>(
          ApiConstants.sendOtp,
          data: {'phone_or_email': normalizeIdentifier(identifier), 'purpose': purpose},
          options: ApiClient.anonymous,
        );
      });

  @override
  Future<Map<String, dynamic>> verifyCode({required String identifier, required String code, required String purpose}) =>
      _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(
          ApiConstants.verifyOtp,
          data: {'phone_or_email': normalizeIdentifier(identifier), 'code': code, 'purpose': purpose},
          options: ApiClient.anonymous,
        );
        return response.data!;
      });

  @override
  Future<void> resetPassword({required String resetToken, required String newPassword}) => _call(() async {
        await apiClient.post<dynamic>(
          ApiConstants.resetPassword,
          data: {'token': resetToken, 'new_password': newPassword},
          options: ApiClient.anonymous,
        );
      });

  @override
  Future<UserModel> currentUser() => _call(() async {
        final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.me);
        return UserModel.fromJson(response.data!);
      });

  @override
  Future<void> logout(String refreshToken) => _call(() async {
        await apiClient.post<dynamic>(ApiConstants.logout, data: {'refresh_token': refreshToken});
      });
}
