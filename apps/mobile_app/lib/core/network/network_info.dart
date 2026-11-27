import 'package:connectivity_plus/connectivity_plus.dart';

abstract class NetworkInfo {
  Future<bool> get isConnected;
}

class NetworkInfoImpl implements NetworkInfo {
  final Connectivity connectivity;

  NetworkInfoImpl(this.connectivity);

  @override
  Future<bool> get isConnected async {
    // One entry per active interface (wifi, mobile, ...); [none] when offline.
    final results = await connectivity.checkConnectivity();
    return results.any((result) => result != ConnectivityResult.none);
  }
}

/// Whether the device has a network: the current state first, then each change. One entry per active
/// interface (wifi, mobile, ...); [ConnectivityResult.none] alone means offline.
Stream<bool> onlineStatus(Connectivity connectivity) async* {
  bool online(List<ConnectivityResult> results) => results.any((r) => r != ConnectivityResult.none);
  yield online(await connectivity.checkConnectivity());
  yield* connectivity.onConnectivityChanged.map(online);
}
