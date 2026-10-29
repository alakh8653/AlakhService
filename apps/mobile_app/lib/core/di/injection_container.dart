import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:get_it/get_it.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/auth/data/datasources/auth_local_datasource.dart';
import '../../features/auth/data/datasources/auth_remote_datasource.dart';
import '../../features/auth/data/repositories/auth_repository_impl.dart';
import '../../features/auth/domain/repositories/auth_repository.dart';
import '../../features/auth/domain/usecases/login_usecase.dart';
import '../../features/auth/domain/usecases/register_usecase.dart';
import '../../features/auth/domain/usecases/session_usecases.dart';
import '../../features/auth/domain/usecases/verify_otp_usecase.dart';
import '../../features/auth/presentation/bloc/auth_bloc.dart';
import '../../features/auth/presentation/bloc/auth_event.dart';
import '../../features/booking/data/availability_api.dart';
import '../../features/booking/data/booking_queue_api.dart';
import '../../features/booking/data/waitlist_api.dart';
import '../../features/booking/data/datasources/booking_remote_datasource.dart';
import '../../features/booking/data/coupon_api.dart';
import '../../features/booking/data/dispute_api.dart';
import '../../features/booking/data/rating_api.dart';
import '../../features/booking/data/repositories/booking_repository_impl.dart';
import '../../features/booking/domain/repositories/booking_repository.dart';
import '../../features/booking/domain/usecases/cancel_booking_usecase.dart';
import '../../features/booking/domain/usecases/create_booking_usecase.dart';
import '../../features/booking/presentation/bloc/booking_bloc.dart';
import '../../features/chat/data/chat_api.dart';
import '../../features/legal/data/legal_api.dart';
import '../../features/notifications/data/notifications_api.dart';
import '../../features/payment/data/payment_api.dart';
import '../../features/jobs/data/location_reporter.dart';
import '../../features/profile/data/address_api.dart';
import '../../features/push/push_service.dart';
import '../../features/profile/data/data_export_api.dart';
import '../../features/profile/data/profile_api.dart';
import '../../features/directions/data/shop_location_api.dart';
import '../../features/queue/data/queue_api.dart';
import '../../features/reviews/data/reviews_api.dart';
import '../../features/services/data/datasources/service_remote_datasource.dart';
import '../../features/loyalty/data/loyalty_api.dart';
import '../../features/packages/data/packages_api.dart';
import '../../features/shops/data/saved_shops_api.dart';
import '../../features/shops/data/team_api.dart';
import '../../features/shops/data/shop_hours_api.dart';
import '../../features/services/data/repositories/service_repository_impl.dart';
import '../../features/services/domain/repositories/service_repository.dart';
import '../../features/services/domain/usecases/get_services_usecase.dart';
import '../../features/services/domain/usecases/search_services_usecase.dart';
import '../../features/services/presentation/bloc/service_bloc.dart';
import '../../features/jobs/data/jobs_api.dart';
import '../../features/tracking/data/tracking_api.dart';
import '../../features/tracking/data/tracking_destination.dart';
import '../network/api_client.dart';
import '../network/network_info.dart';
import '../network/token_store.dart';
import '../settings/app_settings.dart';

final sl = GetIt.instance;

/// Registers the app's dependencies. [tokens] can be swapped for a [MemoryTokenStore] in tests;
/// [push] is the device's push channel, null when Firebase is not configured.
Future<void> init({TokenStore? tokens, PushMessaging? push}) async {
  // Core
  sl.registerLazySingleton<TokenStore>(() => tokens ?? SecureTokenStore());
  sl.registerLazySingleton(
    () => ApiClient(
      tokens: sl(),
      // A rejected refresh ends the session everywhere in the app.
      onSessionExpired: () => sl<AuthBloc>().add(const SessionExpired()),
    ),
  );
  // Theme and language, read before the first frame so the app starts in the chosen ones.
  sl.registerSingleton(SettingsCubit(await SharedPreferences.getInstance()));
  sl.registerLazySingleton(() => Connectivity());
  sl.registerLazySingleton<NetworkInfo>(() => NetworkInfoImpl(sl()));

  // Auth: one bloc for the whole app, so session expiry reaches every screen.
  sl.registerLazySingleton(
    () => AuthBloc(
      loginUseCase: sl(),
      registerUseCase: sl(),
      verifyOtpUseCase: sl(),
      getCurrentUserUseCase: sl(),
      logoutUseCase: sl(),
      resendOtpUseCase: sl(),
    ),
  );
  sl.registerLazySingleton(() => LoginUseCase(sl()));
  sl.registerLazySingleton(() => RegisterUseCase(sl()));
  sl.registerLazySingleton(() => VerifyOtpUseCase(sl()));
  sl.registerLazySingleton(() => GetCurrentUserUseCase(sl()));
  sl.registerLazySingleton(() => LogoutUseCase(sl()));
  sl.registerLazySingleton(() => ResendOtpUseCase(sl()));
  sl.registerLazySingleton<AuthRepository>(
    () => AuthRepositoryImpl(
      remoteDataSource: sl(),
      localDataSource: sl(),
      networkInfo: sl(),
      tokens: sl(),
      beforeSignOut: () => sl<PushService>().releaseDevice(),
    ),
  );
  sl.registerLazySingleton<AuthRemoteDataSource>(() => AuthRemoteDataSourceImpl(apiClient: sl()));
  sl.registerLazySingleton<AuthLocalDataSource>(() => AuthLocalDataSourceImpl());

  // Services catalogue
  sl.registerFactory(() => ServiceBloc(getServicesUseCase: sl(), searchServicesUseCase: sl()));
  sl.registerLazySingleton(() => GetServicesUseCase(sl()));
  sl.registerLazySingleton(() => SearchServicesUseCase(sl()));
  sl.registerLazySingleton<ServiceRepository>(() => ServiceRepositoryImpl(remoteDataSource: sl(), networkInfo: sl()));
  sl.registerLazySingleton<ServiceRemoteDataSource>(() => ServiceRemoteDataSourceImpl(apiClient: sl(), ratings: sl()));
  sl.registerLazySingleton(() => ReviewsApi(sl()));

  // Bookings
  sl.registerFactory(
    () => BookingBloc(createBookingUseCase: sl(), cancelBookingUseCase: sl(), bookingRepository: sl()),
  );
  sl.registerLazySingleton(() => CreateBookingUseCase(sl()));
  sl.registerLazySingleton(() => CancelBookingUseCase(sl()));
  sl.registerLazySingleton<BookingRepository>(() => BookingRepositoryImpl(remoteDataSource: sl(), networkInfo: sl()));
  sl.registerLazySingleton<BookingRemoteDataSource>(
    () => BookingRemoteDataSourceImpl(apiClient: sl(), services: sl()),
  );

  // Smaller features talk to their service directly.
  sl.registerLazySingleton(() => TrackingApi(sl()));
  sl.registerLazySingleton(() => JobsApi(sl(), services: sl()));
  sl.registerLazySingleton(() => QueueApi(sl()));
  sl.registerLazySingleton(() => ShopLocationApi(sl()));
  sl.registerLazySingleton(() => NotificationsApi(sl()));
  sl.registerLazySingleton(() => ProfileApi(sl()));
  sl.registerLazySingleton(() => AddressApi(sl()));
  sl.registerLazySingleton(
    () => TrackingDestinations(shops: sl(), addresses: sl(), device: DeviceLocationSource()),
  );
  sl.registerLazySingleton(() => PaymentApi(sl()));
  sl.registerLazySingleton(() => RatingApi(sl()));
  sl.registerLazySingleton(() => DisputeApi(sl()));
  sl.registerLazySingleton(() => CouponApi(sl()));
  sl.registerLazySingleton(() => AvailabilityApi(sl()));
  sl.registerLazySingleton(() => WaitlistApi(sl()));
  sl.registerLazySingleton(() => BookingQueueApi(sl()));
  sl.registerLazySingleton(() => ShopHoursApi(sl()));
  sl.registerLazySingleton(() => SavedShopsApi(sl()));
  sl.registerLazySingleton(() => TeamApi(sl()));
  sl.registerLazySingleton(() => LoyaltyApi(sl()));
  sl.registerLazySingleton(() => PackagesApi(sl()));
  sl.registerLazySingleton(() => ChatApi(sl()));
  sl.registerLazySingleton(() => LegalApi(sl()));
  sl.registerLazySingleton(() => DataExportApi(sl()));
  sl.registerLazySingleton(() => DeviceTokenApi(sl()));
  sl.registerLazySingleton(() => PushService(messaging: push, api: sl()));
}
