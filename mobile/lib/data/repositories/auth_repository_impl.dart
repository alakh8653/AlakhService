import 'package:dartz/dartz.dart';

import '../../core/constants/app_constants.dart';
import '../../core/errors/exceptions.dart';
import '../../core/errors/failures.dart';
import '../../core/network/network_info.dart';
import '../../domain/entities/user.dart';
import '../../domain/repositories/auth_repository.dart';
import '../datasources/local/local_storage.dart';
import '../datasources/remote/auth_remote_datasource.dart';
import '../models/user_model.dart';

class AuthRepositoryImpl implements AuthRepository {
  const AuthRepositoryImpl({
    required this.remoteDataSource,
    required this.localStorage,
    required this.networkInfo,
  });

  final AuthRemoteDataSource remoteDataSource;
  final LocalStorage localStorage;
  final NetworkInfo networkInfo;

  @override
  Future<Either<Failure, User>> login({
    required String email,
    required String password,
  }) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final data = await remoteDataSource.login(email: email, password: password);
      await _persistTokens(data);
      return Right(UserModel.fromJson(data['user'] as Map<String, dynamic>));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    } on UnauthorizedException catch (e) {
      return Left(AuthFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, User>> register({
    required String name,
    required String email,
    required String password,
    required String phone,
  }) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final data = await remoteDataSource.register(
        name: name,
        email: email,
        password: password,
        phone: phone,
      );
      await _persistTokens(data);
      return Right(UserModel.fromJson(data['user'] as Map<String, dynamic>));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, void>> logout() async {
    try {
      final token = localStorage.getString(AppConstants.refreshTokenKey) ?? '';
      await remoteDataSource.logout(refreshToken: token);
    } catch (_) {
      // Best-effort remote logout; always clear local state.
    }
    await localStorage.remove(AppConstants.authTokenKey);
    await localStorage.remove(AppConstants.refreshTokenKey);
    await localStorage.remove(AppConstants.userIdKey);
    return const Right(null);
  }

  @override
  Future<Either<Failure, void>> forgotPassword({required String email}) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      await remoteDataSource.forgotPassword(email: email);
      return const Right(null);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }

  @override
  Future<Either<Failure, User>> getProfile() async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      final user = await remoteDataSource.getProfile();
      return Right(user);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message, statusCode: e.statusCode));
    }
  }

  @override
  bool get isLoggedIn {
    final token = localStorage.getString(AppConstants.authTokenKey);
    return token != null && token.isNotEmpty;
  }

  Future<void> _persistTokens(Map<String, dynamic> data) async {
    final accessToken = data['access_token'] as String?;
    final refreshToken = data['refresh_token'] as String?;
    if (accessToken != null) {
      await localStorage.setString(AppConstants.authTokenKey, accessToken);
    }
    if (refreshToken != null) {
      await localStorage.setString(AppConstants.refreshTokenKey, refreshToken);
    }
  }
}
