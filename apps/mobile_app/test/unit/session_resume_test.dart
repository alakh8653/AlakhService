import 'package:alakh_service/core/errors/exceptions.dart';
import 'package:alakh_service/core/network/network_info.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/data/datasources/auth_local_datasource.dart';
import 'package:alakh_service/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:alakh_service/features/auth/data/models/user_model.dart';
import 'package:alakh_service/features/auth/data/repositories/auth_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';

class Online implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

/// The server answers /me with [status].
class Remote implements AuthRemoteDataSource {
  final int status;

  Remote(this.status);

  @override
  Future<UserModel> currentUser() async => throw ServerException(message: 'Service unavailable', statusCode: status);

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class Local implements AuthLocalDataSource {
  UserModel? user;

  Local(this.user);

  @override
  Future<void> cacheUser(UserModel user) async => this.user = user;

  @override
  Future<UserModel?> getCachedUser() async => user;

  @override
  Future<void> clearCache() async => user = null;
}

void main() {
  final cached = UserModel.fromJson(const {
    'id': 'u1',
    'full_name': 'Demo Customer',
    'email': 'customer@example.com',
    'role': 'customer',
    'is_verified': true,
    'created_at': '2026-10-01T00:00:00Z',
  });

  Future<AuthRepositoryImpl> repo(int status, UserModel? user) async {
    final tokens = MemoryTokenStore();
    await tokens.save(accessToken: 'a', refreshToken: 'r');
    return AuthRepositoryImpl(remoteDataSource: Remote(status), localDataSource: Local(user), networkInfo: Online(), tokens: tokens);
  }

  test('a server hiccup at start-up keeps the customer signed in as the last known user', () async {
    final result = await (await repo(503, cached)).getCurrentUser();
    expect(result.getOrElse(() => null)?.id, 'u1');
  });

  test('a rejected session still signs out', () async {
    final result = await (await repo(401, cached)).getCurrentUser();
    expect(result.getOrElse(() => cached), isNull);
  });
}
