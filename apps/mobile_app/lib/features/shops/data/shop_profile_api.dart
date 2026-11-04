import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

class WorkPhoto {
  final String id;

  /// Full address of the image.
  final String url;
  final String? caption;

  const WorkPhoto({required this.id, required this.url, this.caption});

  factory WorkPhoto.fromJson(Map<String, dynamic> j) => WorkPhoto(
        id: j['id'] as String,
        url: '${ApiConstants.baseUrl}${j['url']}',
        caption: j['caption'] as String?,
      );
}

/// What a customer sees of a business before booking.
class ShopProfile {
  final String? about;
  final int? yearsExperience;
  final List<String> languages;
  final List<WorkPhoto> photos;

  const ShopProfile({this.about, this.yearsExperience, this.languages = const [], this.photos = const []});

  bool get isEmpty => (about ?? '').isEmpty && yearsExperience == null && languages.isEmpty && photos.isEmpty;
}

class ShopProfileApi {
  final ApiClient apiClient;

  ShopProfileApi(this.apiClient);

  Future<ShopProfile> profile(String shopId) async {
    try {
      final shop = (await apiClient.get<Map<String, dynamic>>(ApiConstants.shop(shopId))).data!;
      final photos = (await apiClient.get<List<dynamic>>('${ApiConstants.shop(shopId)}/photos')).data!;
      return ShopProfile(
        about: shop['description'] as String?,
        yearsExperience: (shop['years_experience'] as num?)?.toInt(),
        languages: ((shop['languages'] as List<dynamic>?) ?? const []).cast<String>(),
        photos: photos.cast<Map<String, dynamic>>().map(WorkPhoto.fromJson).toList(),
      );
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
