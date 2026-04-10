import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import '../core/network/api_client.dart';
import '../core/network/network_info.dart';
import '../data/datasources/local/local_storage.dart';
import '../data/datasources/remote/auth_remote_datasource.dart';
import '../data/datasources/remote/booking_remote_datasource.dart';
import '../data/datasources/remote/service_remote_datasource.dart';
import '../data/repositories/auth_repository_impl.dart';
import '../data/repositories/booking_repository_impl.dart';
import '../data/repositories/service_repository_impl.dart';
import '../domain/repositories/auth_repository.dart';
import '../domain/repositories/booking_repository.dart';
import '../domain/repositories/service_repository.dart';
import '../domain/usecases/create_booking_usecase.dart';
import '../domain/usecases/get_services_usecase.dart';
import '../domain/usecases/login_usecase.dart';
import '../domain/usecases/register_usecase.dart';
import '../presentation/bloc/auth/auth_bloc.dart';
import '../presentation/bloc/booking/booking_bloc.dart';
import '../presentation/bloc/service/service_bloc.dart';

final GetIt sl = GetIt.instance;

Future<void> init() async {
  // Local storage
  await LocalStorage.instance.init();

  // Network
  sl.registerLazySingleton<Dio>(() => ApiClient.instance.dio);
  sl.registerLazySingleton<NetworkInfo>(() => NetworkInfoImpl(Connectivity()));

  // Remote data sources
  sl.registerLazySingleton<AuthRemoteDataSource>(() => AuthRemoteDataSourceImpl(dio: sl()));
  sl.registerLazySingleton<ServiceRemoteDataSource>(() => ServiceRemoteDataSourceImpl(dio: sl()));
  sl.registerLazySingleton<BookingRemoteDataSource>(() => BookingRemoteDataSourceImpl(dio: sl()));

  // Repositories
  sl.registerLazySingleton<AuthRepository>(() => AuthRepositoryImpl(remoteDataSource: sl(), localStorage: LocalStorage.instance, networkInfo: sl()));
  sl.registerLazySingleton<ServiceRepository>(() => ServiceRepositoryImpl(remoteDataSource: sl(), networkInfo: sl()));
  sl.registerLazySingleton<BookingRepository>(() => BookingRepositoryImpl(remoteDataSource: sl(), networkInfo: sl()));

  // Use cases
  sl.registerLazySingleton(() => LoginUseCase(sl()));
  sl.registerLazySingleton(() => RegisterUseCase(sl()));
  sl.registerLazySingleton(() => GetServicesUseCase(sl()));
  sl.registerLazySingleton(() => CreateBookingUseCase(sl()));

  // BLoCs
  sl.registerFactory(() => AuthBloc(loginUseCase: sl(), registerUseCase: sl(), authRepository: sl()));
  sl.registerFactory(() => ServiceBloc(getServicesUseCase: sl(), serviceRepository: sl()));
  sl.registerFactory(() => BookingBloc(createBookingUseCase: sl(), bookingRepository: sl()));
}
