import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../bloc/booking/booking_bloc.dart';
import '../../bloc/booking/booking_event.dart';
import '../../bloc/booking/booking_state.dart';
import '../../../config/routes.dart';
import '../../../core/utils/helpers.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_text_field.dart';
import '../../widgets/loading_indicator.dart';

class BookingPage extends StatefulWidget {
  const BookingPage({super.key, required this.serviceId});

  final String serviceId;

  @override
  State<BookingPage> createState() => _BookingPageState();
}

class _BookingPageState extends State<BookingPage> {
  final _formKey = GlobalKey<FormState>();
  final _addressCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();
  DateTime? _selectedDate;
  TimeOfDay? _selectedTime;

  @override
  void dispose() {
    _addressCtrl.dispose();
    _notesCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime.now().add(const Duration(days: 1)),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 90)),
    );
    if (picked != null) setState(() => _selectedDate = picked);
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );
    if (picked != null) setState(() => _selectedTime = picked);
  }

  String? _buildScheduledAt() {
    if (_selectedDate == null || _selectedTime == null) return null;
    final dt = DateTime(
      _selectedDate!.year,
      _selectedDate!.month,
      _selectedDate!.day,
      _selectedTime!.hour,
      _selectedTime!.minute,
    );
    return dt.toIso8601String();
  }

  void _submit() {
    AppHelpers.dismissKeyboard(context);
    if (!_formKey.currentState!.validate()) return;
    final scheduledAt = _buildScheduledAt();
    if (scheduledAt == null) {
      AppHelpers.showSnackBar(
        context,
        'Please select a date and time.',
        isError: true,
      );
      return;
    }
    context.read<BookingBloc>().add(
          CreateBookingRequested(
            serviceId: widget.serviceId,
            scheduledAt: scheduledAt,
            address: _addressCtrl.text.trim(),
            notes: _notesCtrl.text.trim().isNotEmpty ? _notesCtrl.text.trim() : null,
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<BookingBloc, BookingState>(
      listener: (context, state) {
        if (state is BookingCreated) {
          AppHelpers.showSnackBar(context, 'Booking confirmed!');
          context.go(
            '${Routes.payment}?bookingId=${state.booking.id}',
          );
        } else if (state is BookingError) {
          AppHelpers.showSnackBar(context, state.message, isError: true);
        }
      },
      child: Scaffold(
        appBar: AppBar(title: const Text('Book Service')),
        body: BlocBuilder<BookingBloc, BookingState>(
          builder: (context, state) {
            if (state is BookingLoading) return const LoadingIndicator();
            return SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text('Schedule', style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 12),
                    _DateTimePicker(
                      date: _selectedDate,
                      time: _selectedTime,
                      onPickDate: _pickDate,
                      onPickTime: _pickTime,
                    ),
                    const SizedBox(height: 20),
                    Text('Address', style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 12),
                    CustomTextField(
                      controller: _addressCtrl,
                      label: 'Service address',
                      hint: '123 Main St, City, State',
                      maxLines: 2,
                      prefixIcon: Icons.location_on_outlined,
                      validator: (v) =>
                          AppValidators.required(v, fieldName: 'Address'),
                    ),
                    const SizedBox(height: 16),
                    CustomTextField(
                      controller: _notesCtrl,
                      label: 'Additional notes (optional)',
                      maxLines: 3,
                      prefixIcon: Icons.notes_outlined,
                    ),
                    const SizedBox(height: 32),
                    CustomButton(label: 'Confirm Booking', onPressed: _submit),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _DateTimePicker extends StatelessWidget {
  const _DateTimePicker({
    required this.date,
    required this.time,
    required this.onPickDate,
    required this.onPickTime,
  });

  final DateTime? date;
  final TimeOfDay? time;
  final VoidCallback onPickDate;
  final VoidCallback onPickTime;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            icon: const Icon(Icons.calendar_today_outlined),
            label: Text(date == null
                ? 'Select date'
                : '${date!.day}/${date!.month}/${date!.year}'),
            onPressed: onPickDate,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: OutlinedButton.icon(
            icon: const Icon(Icons.access_time_outlined),
            label: Text(time == null ? 'Select time' : time!.format(context)),
            onPressed: onPickTime,
          ),
        ),
      ],
    );
  }
}

// Make AppValidators accessible without a full import chain in this file
abstract class AppValidators {
  static String? required(String? value, {String? fieldName}) {
    if (value == null || value.trim().isEmpty) {
      return '${fieldName ?? 'This field'} is required.';
    }
    return null;
  }
}
