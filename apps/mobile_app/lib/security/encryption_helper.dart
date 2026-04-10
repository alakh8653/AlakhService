import 'dart:convert';
import 'dart:typed_data';
import 'package:encrypt/encrypt.dart' as enc;

/// AES-256 encryption / decryption helper.
///
/// The key must be exactly 32 bytes (256 bits). The IV is randomly generated
/// on each encryption and prepended (base-64-encoded) to the cipher text,
/// separated by a colon.
class EncryptionHelper {
  final enc.Key _key;

  EncryptionHelper({required String base64Key})
      : _key = enc.Key(
          Uint8List.fromList(base64Decode(base64Key)),
        );

  /// Encrypts [plainText] and returns "<iv>:<cipherText>" (both base64).
  String encrypt(String plainText) {
    final iv = enc.IV.fromSecureRandom(16);
    final encrypter = enc.Encrypter(enc.AES(_key, mode: enc.AESMode.cbc));
    final encrypted = encrypter.encrypt(plainText, iv: iv);
    return '${iv.base64}:${encrypted.base64}';
  }

  /// Decrypts a value produced by [encrypt].
  String decrypt(String cipherText) {
    final parts = cipherText.split(':');
    if (parts.length != 2) throw ArgumentError('Invalid cipher text format');
    final iv = enc.IV.fromBase64(parts[0]);
    final encrypter = enc.Encrypter(enc.AES(_key, mode: enc.AESMode.cbc));
    return encrypter.decrypt64(parts[1], iv: iv);
  }

  /// Generates a random 32-byte key encoded as base64. Useful for key setup.
  static String generateKey() {
    final key = enc.Key.fromSecureRandom(32);
    return key.base64;
  }

  /// Encrypts a JSON-serialisable [map] and returns the cipher string.
  String encryptMap(Map<String, dynamic> map) =>
      encrypt(jsonEncode(map));

  /// Decrypts a cipher string back to a [Map].
  Map<String, dynamic> decryptMap(String cipherText) =>
      jsonDecode(decrypt(cipherText)) as Map<String, dynamic>;
}
