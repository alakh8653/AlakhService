import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/errors/exceptions.dart';
import '../../models/user_model.dart';

abstract class AuthRemoteDataSource {
  Future<Map<String, dynamic>> login({required String email, required String password});
  Future<Map<String, dynamic>> register({
    required String name,
    required String email,
    required String password,
    required String phone,
  });
  Future<void> logout({required String refreshToken});
  Future<Map<String, dynamic>> refreshToken({required String token});
  Future<void> forgotPassword({required String email});
  Future<UserModel> getProfile();
}

class AuthRemoteDataSourceImpl implements AuthRemoteDataSource {
  const AuthRemoteDataSourceImpl({required this.dio});

  final Dio dio;

  @override
  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final response = await dio.post(
      ApiConstants.login,
      data: {'email': email, 'password': password},
    );
    _assertSuccess(response);
    return response.data as Map<String, dynamic>;
  }

  @override
  Future<Map<String, dynamic>> register({
    required String name,
    required String email,
    required String password,
    required String phone,
  }) async {
    final response = await dio.post(
      ApiConstants.register,
      data: {'name': name, 'email': email, 'password': password, 'phone': phone},
    );
    _assertSuccess(response);
    return response.data as Map<String, dynamic>;
  }

  @override
  Future<void> logout({required String refreshToken}) async {
    await dio.post(ApiConstants.logout, data: {'refresh_token': refreshToken});
  }

  @override
  Future<Map<String, dynamic>> refreshToken({required String token}) async {
    final response = await dio.post(
      ApiConstants.refreshToken,
      data: {'refresh_token': token},
    );
    _assertSuccess(response);
    return response.data as Map<String, dynamic>;
  }

  @override
  Future<void> forgotPassword({required String email}) async {
    final response = await dio.post(
      ApiConstants.forgotPassword,
      data: {'email': email},
    );
    _assertSuccess(response);
  }

  @override
  Future<UserModel> getProfile() async {
    final response = await dio.get(ApiConstants.profile);
    _assertSuccess(response);
    return UserModel.fromJson(response.data as Map<String, dynamic>);
  }

  void _assertSuccess(Response<dynamic> response) {
    if (response.statusCode == null || response.statusCode! >= 400) {
      throw ServerException(
        message: response.data?['message']?.toString() ?? 'Unknown server error',
        statusCode: response.statusCode,
      );
    }
  }
}
