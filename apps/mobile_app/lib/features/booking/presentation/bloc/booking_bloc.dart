import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/usecases/create_booking_usecase.dart';
import '../../domain/usecases/cancel_booking_usecase.dart';
import '../../domain/repositories/booking_repository.dart';
import 'booking_event.dart';
import 'booking_state.dart';

class BookingBloc extends Bloc<BookingEvent, BookingState> {
  final CreateBookingUseCase createBookingUseCase;
  final CancelBookingUseCase cancelBookingUseCase;
  final BookingRepository bookingRepository;

  BookingBloc({
    required this.createBookingUseCase,
    required this.cancelBookingUseCase,
    required this.bookingRepository,
  }) : super(const BookingInitial()) {
    on<CreateBookingRequested>(_onCreateBooking);
    on<LoadUserBookings>(_onLoadBookings);
    on<CancelBookingRequested>(_onCancelBooking);
    on<RefreshBookings>(_onRefreshBookings);
  }

  Future<void> _onCreateBooking(
    CreateBookingRequested event,
    Emitter<BookingState> emit,
  ) async {
    emit(const BookingLoading());
    final result = await createBookingUseCase(
      CreateBookingParams(
        serviceId: event.serviceId,
        scheduledAt: event.scheduledAt,
        address: event.address,
        notes: event.notes,
        couponCode: event.couponCode,
        delivery: event.delivery,
        idempotencyKey: event.idempotencyKey,
        usePoints: event.usePoints,
        packagePurchaseId: event.packagePurchaseId,
      ),
    );
    result.fold(
      (failure) => emit(BookingError(failure.message)),
      (booking) => emit(BookingCreated(booking)),
    );
  }

  Future<void> _onLoadBookings(
    LoadUserBookings event,
    Emitter<BookingState> emit,
  ) async {
    emit(const BookingLoading());
    final result = await bookingRepository.getUserBookings(page: event.page);
    result.fold(
      (failure) => emit(BookingError(failure.message)),
      (bookings) => emit(BookingsLoaded(bookings)),
    );
  }

  /// Cancels without replacing the list with a spinner: the list stays on screen, then reloads
  /// quietly. A refusal is reported as [BookingActionFailed] and the list comes back unchanged.
  Future<void> _onCancelBooking(
    CancelBookingRequested event,
    Emitter<BookingState> emit,
  ) async {
    final shown = state;
    final result = await cancelBookingUseCase(event.bookingId);
    await result.fold(
      (failure) async {
        emit(BookingActionFailed(failure.message));
        if (shown is BookingsLoaded) emit(shown);
      },
      (_) async {
        emit(BookingCancelled(event.bookingId));
        await _reloadQuietly(emit, fallback: shown);
      },
    );
  }

  /// Reloads the list without showing a spinner; on failure keeps what was shown (or reports it).
  Future<void> _reloadQuietly(Emitter<BookingState> emit, {BookingState? fallback}) async {
    final result = await bookingRepository.getUserBookings();
    result.fold(
      (failure) => emit(fallback is BookingsLoaded ? fallback : BookingError(failure.message)),
      (bookings) => emit(BookingsLoaded(bookings)),
    );
  }

  /// Pull-to-refresh: the list stays visible while it reloads (the refresh indicator shows progress).
  Future<void> _onRefreshBookings(
    RefreshBookings event,
    Emitter<BookingState> emit,
  ) async {
    final shown = state;
    if (shown is! BookingsLoaded) return _onLoadBookings(const LoadUserBookings(), emit);
    final result = await bookingRepository.getUserBookings();
    result.fold(
      (failure) {
        emit(BookingActionFailed(failure.message));
        emit(shown);
      },
      (bookings) => emit(BookingsLoaded(bookings)),
    );
  }
}
