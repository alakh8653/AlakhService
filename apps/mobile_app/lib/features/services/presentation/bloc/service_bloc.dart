import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/usecases/get_services_usecase.dart';
import '../../domain/usecases/search_services_usecase.dart';
import 'service_event.dart';
import 'service_state.dart';

class ServiceBloc extends Bloc<ServiceEvent, ServiceState> {
  final GetServicesUseCase getServicesUseCase;
  final SearchServicesUseCase searchServicesUseCase;

  ServiceBloc({
    required this.getServicesUseCase,
    required this.searchServicesUseCase,
  }) : super(const ServiceInitial()) {
    on<LoadServices>(_onLoadServices);
    on<SearchServices>(_onSearchServices);
    on<RefreshServices>(_onRefreshServices);
  }

  // Each load or search gets a number; a reply that arrives after a newer request was made is
  // dropped, so typing "hair" then "haircut" can't end on the results for "hair".
  int _latest = 0;

  Future<void> _onLoadServices(
    LoadServices event,
    Emitter<ServiceState> emit,
  ) async {
    final request = ++_latest;
    emit(const ServiceLoading());
    final result = await getServicesUseCase(
      GetServicesParams(page: event.page, category: event.category),
    );
    if (request != _latest) return;
    result.fold(
      (failure) => emit(ServiceError(message: failure.message)),
      (services) => emit(
        ServicesLoaded(
          services: services,
          currentPage: event.page,
          hasMore: services.length == 20,
        ),
      ),
    );
  }

  Future<void> _onSearchServices(
    SearchServices event,
    Emitter<ServiceState> emit,
  ) async {
    final request = ++_latest;
    emit(const ServiceLoading());
    final result = await searchServicesUseCase(
      SearchServicesParams(query: event.query, category: event.category),
    );
    if (request != _latest) return;
    result.fold(
      (failure) => emit(ServiceError(message: failure.message)),
      (results) =>
          emit(ServiceSearchResults(results: results, query: event.query)),
    );
  }

  Future<void> _onRefreshServices(
    RefreshServices event,
    Emitter<ServiceState> emit,
  ) async {
    add(const LoadServices());
  }
}
