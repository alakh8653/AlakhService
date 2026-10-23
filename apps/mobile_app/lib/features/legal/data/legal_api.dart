import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';

/// Where the legal pages live. Set per build with `--dart-define=LEGAL_BASE_URL=https://example.in`.
/// PLACEHOLDER: replace the default with the real site before release.
class LegalLinks {
  LegalLinks._();

  static const String baseUrl = String.fromEnvironment('LEGAL_BASE_URL', defaultValue: 'https://alakhservice.in');

  /// The Terms version this build was written against, sent when the server can't be asked.
  static const String fallbackTermsVersion = '2026-10';
}

/// The current Terms version and the legal pages (GET /api/v1/legal/current, public).
class LegalInfo {
  final String termsVersion;
  final String termsUrl;
  final String privacyUrl;
  final String refundUrl;
  final String grievanceUrl;

  const LegalInfo({
    required this.termsVersion,
    required this.termsUrl,
    required this.privacyUrl,
    required this.refundUrl,
    required this.grievanceUrl,
  });

  /// The build's own links and version, for when the server can't be reached.
  static const fallback = LegalInfo(
    termsVersion: LegalLinks.fallbackTermsVersion,
    termsUrl: '${LegalLinks.baseUrl}/terms',
    privacyUrl: '${LegalLinks.baseUrl}/privacy',
    refundUrl: '${LegalLinks.baseUrl}/refunds',
    grievanceUrl: '${LegalLinks.baseUrl}/grievance',
  );

  factory LegalInfo.fromJson(Map<String, dynamic> json) {
    String pick(String key, String fallback) {
      final value = json[key];
      return value is String && value.isNotEmpty ? value : fallback;
    }

    return LegalInfo(
      termsVersion: pick('terms_version', LegalInfo.fallback.termsVersion),
      termsUrl: pick('terms_url', LegalInfo.fallback.termsUrl),
      privacyUrl: pick('privacy_url', LegalInfo.fallback.privacyUrl),
      refundUrl: pick('refund_url', LegalInfo.fallback.refundUrl),
      grievanceUrl: pick('grievance_url', LegalInfo.fallback.grievanceUrl),
    );
  }
}

class LegalApi {
  final ApiClient apiClient;

  LegalApi(this.apiClient);

  LegalInfo? _cached;

  /// The server's current legal info, or [LegalInfo.fallback] if it can't be read. Never throws.
  Future<LegalInfo> current() async {
    final cached = _cached;
    if (cached != null) return cached;
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.legalCurrent, options: ApiClient.anonymous);
      return _cached = LegalInfo.fromJson(response.data ?? const {});
    } catch (_) {
      return LegalInfo.fallback;
    }
  }
}
