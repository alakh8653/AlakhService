import 'package:alakh_service/core/constants/api_constants.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/api_errors.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

void main() {
  late MemoryTokenStore tokens;

  setUp(() async {
    tokens = MemoryTokenStore();
    await tokens.save(accessToken: 'old-access', refreshToken: 'refresh-1');
  });

  test('sends the stored access token', () async {
    final adapter = FakeAdapter((_) => (status: 200, body: {'ok': true}));
    final client = ApiClient(dio: fakeDio(adapter), tokens: tokens);

    await client.get<dynamic>('/bookings');

    expect(adapter.requests.single.headers['Authorization'], 'Bearer old-access');
  });

  test('anonymous calls carry no token', () async {
    final adapter = FakeAdapter((_) => (status: 200, body: {}));
    final client = ApiClient(dio: fakeDio(adapter), tokens: tokens);

    await client.post<dynamic>(ApiConstants.login, data: {}, options: ApiClient.anonymous);

    expect(adapter.requests.single.headers.containsKey('Authorization'), isFalse);
  });

  test('refreshes an expired token once and retries the request', () async {
    final adapter = FakeAdapter((r) {
      if (r.path == ApiConstants.refreshToken) {
        return (status: 200, body: {'access_token': 'new-access', 'refresh_token': 'refresh-2'});
      }
      final auth = r.headers['Authorization'];
      return auth == 'Bearer new-access' ? (status: 200, body: {'items': []}) : (status: 401, body: {'detail': 'expired'});
    });
    final client = ApiClient(dio: fakeDio(adapter), tokens: tokens);

    final response = await client.get<Map<String, dynamic>>('/bookings');

    expect(response.data, {'items': []});
    expect(adapter.requests.map((r) => r.path), ['/bookings', ApiConstants.refreshToken, '/bookings']);
    expect(adapter.requests[1].data, {'refresh_token': 'refresh-1'});
    expect(await tokens.accessToken(), 'new-access');
    expect(await tokens.refreshToken(), 'refresh-2');
  });

  test('ends the session when the refresh token is rejected', () async {
    var expired = false;
    final adapter = FakeAdapter((_) => (status: 401, body: {'detail': 'Invalid token'}));
    final client = ApiClient(dio: fakeDio(adapter), tokens: tokens, onSessionExpired: () => expired = true);

    await expectLater(client.get<dynamic>('/bookings'), throwsA(isA<DioException>()));

    expect(expired, isTrue);
    expect(await tokens.accessToken(), isNull);
  });

  test('error messages come from the API detail', () async {
    final adapter = FakeAdapter((_) => (status: 409, body: {'detail': 'Slot already taken'}));
    final client = ApiClient(dio: fakeDio(adapter), tokens: tokens);

    try {
      await client.post<dynamic>('/bookings', data: {});
      fail('expected an error');
    } catch (e) {
      expect(apiErrorMessage(e), 'Slot already taken');
      expect(toServerException(e as DioException).statusCode, 409);
    }
  });
}
