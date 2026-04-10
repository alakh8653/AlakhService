import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../domain/usecases/get_services_usecase.dart';
import '../../../domain/repositories/service_repository.dart';
import 'service_event.dart';
import 'service_state.dart';

class ServiceBloc extends Bloc<ServiceEvent, ServiceState> {
  ServiceBloc({
    required GetServicesUseCase getServicesUseCase,
    required ServiceRepository serviceRepository,
  })  : _getServicesUseCase = getServicesUseCase,
        _serviceRepository = serviceRepository,
        super(ServiceInitial()) {
    on<LoadServices>(_onLoadServices);
    on<LoadMoreServices>(_onLoadMoreServices);
    on<RefreshServices>(_onRefreshServices);
    on<LoadServiceDetail>(_onLoadServiceDetail);
    on<FilterByCategory>(_onFilterByCategory);
  }

  final GetServicesUseCase _getServicesUseCase;
  final ServiceRepository _serviceRepository;

  int _currentPage = 1;
  String? _currentCategory;

  Future<void> _onLoadServices(
    LoadServices event,
    Emitter<ServiceState> emit,
  ) async {
    emit(ServiceLoading());
    _currentPage = 1;
    _currentCategory = event.category;
    final result = await _getServicesUseCase(
      GetServicesParams(page: _currentPage, category: event.category),
    );
    result.fold(
      (failure) => emit(ServiceError(failure.message)),
      (services) => emit(
        ServiceLoaded(
          services: services,
          selectedCategory: event.category,
          hasMore: services.length >= 20,
        ),
      ),
    );
  }

  Future<void> _onLoadMoreServices(
    LoadMoreServices event,
    Emitter<ServiceState> emit,
  ) async {
    final current = state;
    if (current is! ServiceLoaded || !current.hasMore) return;

    emit(ServiceLoadingMore(
      services: current.services,
      selectedCategory: current.selectedCategory,
    ));

    _currentPage++;
    final result = await _getServicesUseCase(
      GetServicesParams(page: _currentPage, category: _currentCategory),
    );
    result.fold(
      (failure) => emit(ServiceError(failure.message)),
      (newServices) => emit(
        ServiceLoaded(
          services: [...current.services, ...newServices],
          selectedCategory: _currentCategory,
          hasMore: newServices.length >= 20,
        ),
      ),
    );
  }

  Future<void> _onRefreshServices(
    RefreshServices event,
    Emitter<ServiceState> emit,
  ) async {
    add(LoadServices(category: _currentCategory));
  }

  Future<void> _onLoadServiceDetail(
    LoadServiceDetail event,
    Emitter<ServiceState> emit,
  ) async {
    emit(ServiceLoading());
    final result = await _serviceRepository.getServiceById(event.serviceId);
    result.fold(
      (failure) => emit(ServiceError(failure.message)),
      (service) => emit(ServiceDetailLoaded(service)),
    );
  }

  Future<void> _onFilterByCategory(
    FilterByCategory event,
    Emitter<ServiceState> emit,
  ) async {
    add(LoadServices(category: event.category));
  }
}
