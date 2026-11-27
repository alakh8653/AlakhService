import 'package:equatable/equatable.dart';

/// How results are ordered.
enum ServiceSort {
  /// Best match for a search; by name when browsing.
  recommended('relevance'),
  nearest('distance'),
  priceLow('price_asc'),
  priceHigh('price_desc'),
  topRated('rating');

  /// As service_catalog names it.
  final String api;
  const ServiceSort(this.api);
}

/// What the customer narrowed browsing or search to.
class ServiceFilters extends Equatable {
  final ServiceSort sort;

  /// Only services a professional can do at the customer's home.
  final bool homeVisit;

  /// Only shops rated at least this (4.0 = "4★ & up").
  final double? minRating;

  /// Only services up to this price, in rupees.
  final double? maxPrice;

  /// Where the customer is, for the nearest-first order and distances on the results.
  final double? latitude;
  final double? longitude;

  const ServiceFilters({
    this.sort = ServiceSort.recommended,
    this.homeVisit = false,
    this.minRating,
    this.maxPrice,
    this.latitude,
    this.longitude,
  });

  static const none = ServiceFilters();

  bool get located => latitude != null && longitude != null;

  /// How many filters (not counting the order) are on.
  int get count => (homeVisit ? 1 : 0) + (minRating != null ? 1 : 0) + (maxPrice != null ? 1 : 0);

  ServiceFilters copyWith({
    ServiceSort? sort,
    bool? homeVisit,
    double? Function()? minRating,
    double? Function()? maxPrice,
    (double, double)? Function()? at,
  }) {
    final place = at == null ? (located ? (latitude!, longitude!) : null) : at();
    return ServiceFilters(
      sort: sort ?? this.sort,
      homeVisit: homeVisit ?? this.homeVisit,
      minRating: minRating == null ? this.minRating : minRating(),
      maxPrice: maxPrice == null ? this.maxPrice : maxPrice(),
      latitude: place?.$1,
      longitude: place?.$2,
    );
  }

  /// Query parameters for service_catalog's /services and /services/search.
  Map<String, dynamic> toQuery() => {
        if (sort != ServiceSort.recommended && (sort != ServiceSort.nearest || located)) 'sort': sort.api,
        if (homeVisit) 'mode': 'AT_HOME',
        if (minRating != null) 'min_rating': minRating,
        if (maxPrice != null) 'max_price': maxPrice,
        if (located) ...{'lat': latitude, 'lng': longitude},
      };

  @override
  List<Object?> get props => [sort, homeVisit, minRating, maxPrice, latitude, longitude];
}
