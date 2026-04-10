import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../domain/usecases/create_booking_usecase.dart';
import '../../../domain/repositories/booking_repository.dart';
import 'booking_event.dart';
import 'booking_state.dart';

class BookingBloc extends Bloc<BookingEvent, BookingState> {
  BookingBloc({
    required CreateBookingUseCase createBookingUseCase,
    required BookingRepository bookingRepository,
  })  : _createBookingUseCase = createBookingUseCase,
        _bookingRepository = bookingRepository,
        super(BookingInitial()) {
    on<CreateBookingRequested>(_onCreateBookingRequested);
    on<LoadBookings>(_onLoadBookings);
    on<LoadBookingDetail>(_onLoadBookingDetail);
    on<CancelBookingRequested>(_onCancelBookingRequested);
  }

  final CreateBookingUseCase _createBookingUseCase;
  final BookingRepository _bookingRepository;

  Future<void> _onCreateBookingRequested(
    CreateBookingRequested event,
    Emitter<BookingState> emit,
  ) async {
    emit(BookingLoading());
    final result = await _createBookingUseCase(
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
    LoadBookings event,
    Emitter<BookingState> emit,
  ) async {
    emit(BookingLoading());
    final result = await _bookingRepository.getBookings();
    result.fold(
      (failure) => emit(BookingError(failure.message)),
      (bookings) => emit(BookingsLoaded(bookings)),
    );
  }

  Future<void> _onLoadBookingDetail(
    LoadBookingDetail event,
    Emitter<BookingState> emit,
  ) async {
    emit(BookingLoading());
    final result = await _bookingRepository.getBookingById(event.bookingId);
    result.fold(
      (failure) => emit(BookingError(failure.message)),
      (booking) => emit(BookingDetailLoaded(booking)),
    );
  }

  Future<void> _onCancelBookingRequested(
    CancelBookingRequested event,
    Emitter<BookingState> emit,
  ) async {
    emit(BookingLoading());
    final result = await _bookingRepository.cancelBooking(event.bookingId);
    result.fold(
      (failure) => emit(BookingError(failure.message)),
      (booking) => emit(BookingCancelled(booking)),
    );
  }
}
