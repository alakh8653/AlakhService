import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:alakh_service/core/network/network_info.dart';

class _FakeConnectivity extends Fake implements Connectivity {
  _FakeConnectivity(this.results);

  final List<ConnectivityResult> results;

  @override
  Future<List<ConnectivityResult>> checkConnectivity() async => results;
}

void main() {
  Future<bool> isConnected(List<ConnectivityResult> results) =>
      NetworkInfoImpl(_FakeConnectivity(results)).isConnected;

  test('is offline when the only result is none', () async {
    expect(await isConnected([ConnectivityResult.none]), isFalse);
  });

  test('is online with any active interface', () async {
    expect(await isConnected([ConnectivityResult.wifi]), isTrue);
    expect(
      await isConnected([ConnectivityResult.mobile, ConnectivityResult.vpn]),
      isTrue,
    );
  });
}
