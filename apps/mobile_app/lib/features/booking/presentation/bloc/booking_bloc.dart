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

  Future<void> _onCancelBooking(
    CancelBookingRequested event,
    Emitter<BookingState> emit,
  ) async {
    emit(const BookingLoading());
    final result = await cancelBookingUseCase(event.bookingId);
    result.fold(
      (failure) => emit(BookingError(failure.message)),
      (_) => emit(BookingCancelled(event.bookingId)),
    );
  }

  Future<void> _onRefreshBookings(
    RefreshBookings event,
    Emitter<BookingState> emit,
  ) async {
    add(const LoadUserBookings());
  }
}
