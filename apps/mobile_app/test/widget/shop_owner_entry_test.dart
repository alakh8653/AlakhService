import 'package:alakh_service/app/home_shell.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/domain/entities/user.dart';
import 'package:alakh_service/features/jobs/data/jobs_api.dart';
import 'package:alakh_service/features/shop_line/data/shop_line_api.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  group('remembering why someone joined', () {
    test('nothing saved means a customer', () async {
      SharedPreferences.setMockInitialValues({});
      expect(await OwnerIntent.read(), isFalse);
    });

    test('offering services is remembered, and can be taken back', () async {
      SharedPreferences.setMockInitialValues({});
      await OwnerIntent.save(true);
      expect(await OwnerIntent.read(), isTrue);
      await OwnerIntent.save(false);
      expect(await OwnerIntent.read(), isFalse);
    });
  });

  test('the shell still takes its API overrides', () {
    final user = User(
      id: 'u1',
      name: 'Ravi',
      phone: '+919876543210',
      role: 'user',
      isVerified: true,
      createdAt: DateTime(2026),
    );
    final client = ApiClient(dio: Dio(), tokens: MemoryTokenStore());
    final shell = HomeShell(
      user: user,
      jobsApi: JobsApi(client),
      shopLineApi: ShopLineApi(client),
      ownerApi: ShopOwnerApi(client),
    );
    expect(shell.ownerApi, isNotNull);
  });
}
