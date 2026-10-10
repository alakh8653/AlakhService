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
