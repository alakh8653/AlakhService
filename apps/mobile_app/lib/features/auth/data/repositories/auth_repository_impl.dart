import 'package:dartz/dartz.dart';
import '../../../../core/errors/exceptions.dart';
import '../../../../core/errors/failures.dart';
import '../../../../core/network/network_info.dart';
import '../../../../core/network/token_store.dart';
import '../../domain/entities/user.dart';
import '../../domain/repositories/auth_repository.dart';
import '../datasources/auth_remote_datasource.dart';
import '../datasources/auth_local_datasource.dart';
import '../models/user_model.dart';

class AuthRepositoryImpl implements AuthRepository {
  final AuthRemoteDataSource remoteDataSource;
  final AuthLocalDataSource localDataSource;
  final NetworkInfo networkInfo;
  final TokenStore tokens;

  AuthRepositoryImpl({
    required this.remoteDataSource,
    required this.localDataSource,
    required this.networkInfo,
    required this.tokens,
  });

  Future<Either<Failure, T>> _online<T>(Future<T> Function() action) async {
    if (!await networkInfo.isConnected) return const Left(NetworkFailure());
    try {
      return Right(await action());
    } on ServerException catch (e) {
      return Left(ServerFailure(message: e.message, statusCode: e.statusCode));
    }
  }

  /// Stores the session and loads the user it belongs to.
  Future<User> _startSession(TokenPair pair) async {
    await tokens.save(accessToken: pair.accessToken, refreshToken: pair.refreshToken);
    final user = await remoteDataSource.currentUser();
    await localDataSource.cacheUser(user);
    return user;
  }

  @override
  Future<Either<Failure, User>> login({required String phone, required String password}) =>
      _online(() async => _startSession(await remoteDataSource.login(identifier: phone, password: password)));

  @override
  Future<Either<Failure, bool>> register({
    required String name,
    required String phone,
    required String password,
    required String role,
  }) =>
      _online(() async {
        await remoteDataSource.register(name: name, phone: phone, password: password);
        await remoteDataSource.sendCode(identifier: phone, purpose: 'registration');
        return true;
      });

  @override
  Future<Either<Failure, User>> verifyOtp({required String phone, required String otp, String purpose = 'registration'}) =>
      _online(() async {
        final result = await remoteDataSource.verifyCode(identifier: phone, code: otp, purpose: purpose);
        return _startSession(TokenPair.fromJson(result));
      });

  @override
  Future<Either<Failure, bool>> resendOtp(String phone, {String purpose = 'registration'}) => _online(() async {
        await remoteDataSource.sendCode(identifier: phone, purpose: purpose);
        return true;
      });

  @override
  Future<Either<Failure, bool>> logout() async {
    final refresh = await tokens.refreshToken();
    if (refresh != null) {
      try {
        await remoteDataSource.logout(refresh);
      } on ServerException {
        // Signing out locally still ends the session on this device.
      }
    }
    await tokens.clear();
    await localDataSource.clearCache();
    return const Right(true);
  }

  @override
  Future<Either<Failure, bool>> forgotPassword(String phone) => _online(() async {
        await remoteDataSource.sendCode(identifier: phone, purpose: 'password_reset');
        return true;
      });

  @override
  Future<Either<Failure, bool>> resetPassword({
    required String phone,
    required String code,
    required String newPassword,
  }) =>
      _online(() async {
        final result = await remoteDataSource.verifyCode(identifier: phone, code: code, purpose: 'password_reset');
        await remoteDataSource.resetPassword(resetToken: result['reset_token'] as String, newPassword: newPassword);
        return true;
      });

  @override
  Future<Either<Failure, User?>> getCurrentUser() async {
    if (await tokens.accessToken() == null) return const Right(null);
    if (!await networkInfo.isConnected) {
      // Offline: carry on with the last known user; requests will fail until back online.
      try {
        return Right(await localDataSource.getCachedUser());
      } on CacheException catch (e) {
        return Left(CacheFailure(message: e.message));
      }
    }
    try {
      final user = await remoteDataSource.currentUser();
      await localDataSource.cacheUser(user);
      return Right(user);
    } on ServerException catch (e) {
      if (e.statusCode == 401) {
        await tokens.clear();
        await localDataSource.clearCache();
        return const Right(null);
      }
      return Left(ServerFailure(message: e.message, statusCode: e.statusCode));
    }
  }
}
