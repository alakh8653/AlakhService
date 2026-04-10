import '../../../../core/network/api_client.dart';
import '../../../../core/constants/api_constants.dart';
import '../../../../core/errors/exceptions.dart';
import '../models/user_model.dart';

abstract class AuthRemoteDataSource {
  Future<UserModel> login({required String phone, required String password});

  Future<bool> register({
    required String name,
    required String phone,
    required String password,
    required String role,
  });

  Future<UserModel> verifyOtp({required String phone, required String otp});

  Future<bool> logout();

  Future<bool> forgotPassword(String phone);
}

class AuthRemoteDataSourceImpl implements AuthRemoteDataSource {
  final ApiClient apiClient;

  AuthRemoteDataSourceImpl({required this.apiClient});

  @override
  Future<UserModel> login({
    required String phone,
    required String password,
  }) async {
    try {
      final response = await apiClient.post(
        ApiConstants.login,
        data: {'phone': phone, 'password': password},
      );
      return UserModel.fromJson(
        response.data['user'] as Map<String, dynamic>,
      );
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }

  @override
  Future<bool> register({
    required String name,
    required String phone,
    required String password,
    required String role,
  }) async {
    try {
      await apiClient.post(
        ApiConstants.register,
        data: {
          'name': name,
          'phone': phone,
          'password': password,
          'role': role,
        },
      );
      return true;
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }

  @override
  Future<UserModel> verifyOtp({
    required String phone,
    required String otp,
  }) async {
    try {
      final response = await apiClient.post(
        ApiConstants.verifyOtp,
        data: {'phone': phone, 'otp': otp},
      );
      return UserModel.fromJson(
        response.data['user'] as Map<String, dynamic>,
      );
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }

  @override
  Future<bool> logout() async {
    try {
      await apiClient.post(ApiConstants.logout);
      return true;
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }

  @override
  Future<bool> forgotPassword(String phone) async {
    try {
      await apiClient.post(
        ApiConstants.forgotPassword,
        data: {'phone': phone},
      );
      return true;
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }
}
