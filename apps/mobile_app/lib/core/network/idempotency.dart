import 'dart:math';

/// A random key that lets the server recognise retries of one request (letters and digits only, so it
/// fits every service's key format).
String newIdempotencyKey({int length = 32}) {
  final random = Random.secure();
  return List.generate(length, (_) => random.nextInt(16).toRadixString(16)).join();
}
