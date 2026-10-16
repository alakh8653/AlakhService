import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/custom_text_field.dart';
import '../../../../shared/utils/validators.dart';
import '../../../profile/data/address_api.dart';
import '../../../services/domain/entities/service_entity.dart';
import '../../domain/entities/booking.dart';
import '../../data/coupon_api.dart';
import '../bloc/booking_bloc.dart';
import '../bloc/booking_event.dart';
import '../bloc/booking_state.dart';

class BookingPage extends StatefulWidget {
  final String serviceId;
  final String serviceName;
  final double servicePrice;
  final CouponApi? couponApi;
  final AddressApi? addressApi;

  /// The ways the service is offered (ServiceMode values) and their extra fees.
  final List<String> serviceModes;
  final double homeVisitFee;
  final double pickupFee;

  const BookingPage({
    super.key,
    required this.serviceId,
    required this.serviceName,
    required this.servicePrice,
    this.couponApi,
    this.addressApi,
    this.serviceModes = const [ServiceMode.atShop],
    this.homeVisitFee = 0,
    this.pickupFee = 0,
  });

  @override
  State<BookingPage> createState() => _BookingPageState();
}

class _BookingPageState extends State<BookingPage> {
  final _formKey = GlobalKey<FormState>();
  final _notesController = TextEditingController();
  final _couponController = TextEditingController();
  final _itemController = TextEditingController();
  CouponCheck? _coupon;
  List<SavedAddress> _saved = const [];
  late String _mode = widget.serviceModes.isEmpty ? ServiceMode.atShop : widget.serviceModes.first;
  SavedAddress? _address;
  bool _checkingCoupon = false;
  DateTime? _selectedDate;
  TimeOfDay? _selectedTime;

  @override
  void initState() {
    super.initState();
    (widget.addressApi ?? sl<AddressApi>()).list().then((saved) {
      if (!mounted || saved.isEmpty) return;
      setState(() {
        _saved = saved;
        _address ??= saved.first; // the default address comes first
      });
    }).catchError((Object _) {});
  }

  @override
  void dispose() {
    _notesController.dispose();
    _couponController.dispose();
    _itemController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: DateTime.now().add(const Duration(days: 1)),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 30)),
    );
    if (date != null) setState(() => _selectedDate = date);
  }

  Future<void> _pickTime() async {
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );
    if (time != null) setState(() => _selectedTime = time);
  }

  Future<void> _applyCoupon() async {
    final code = _couponController.text.trim();
    if (code.isEmpty) return setState(() => _coupon = null);
    setState(() => _checkingCoupon = true);
    try {
      final check = await (widget.couponApi ?? sl<CouponApi>()).check(code);
      if (mounted) setState(() => _coupon = check);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _checkingCoupon = false);
    }
  }

  bool get _needsAddress => ServiceMode.needsAddress.contains(_mode);

  double get _fee => switch (_mode) {
        ServiceMode.atHome => widget.homeVisitFee,
        ServiceMode.pickupDrop => widget.pickupFee,
        _ => 0,
      };

  /// What the customer will pay: the coupon discounts the service, and the visit or pickup fee is
  /// added on top (as booking_service prices it).
  double get _price {
    final coupon = _coupon;
    final service = coupon == null || !coupon.isValid ? widget.servicePrice : widget.servicePrice * (1 - coupon.discountPct / 100);
    return service + _fee;
  }

  double get _listPrice => widget.servicePrice + _fee;

  void _onBook() {
    if (_formKey.currentState?.validate() ?? false) {
      if (_selectedDate == null || _selectedTime == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please select date and time')),
        );
        return;
      }
      if (_needsAddress && _address == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Choose the address we should come to')),
        );
        return;
      }
      final scheduledAt = DateTime(
        _selectedDate!.year,
        _selectedDate!.month,
        _selectedDate!.day,
        _selectedTime!.hour,
        _selectedTime!.minute,
      );
      context.read<BookingBloc>().add(
            CreateBookingRequested(
              serviceId: widget.serviceId,
              scheduledAt: scheduledAt,
              // At the shop nobody comes to the customer, so no address goes with it.
              address: _needsAddress ? _address!.oneLine : '',
              notes: _notesController.text.trim().isEmpty
                  ? null
                  : _notesController.text.trim(),
              // Only a code that checked out is sent; the server applies it to the catalogue price.
              couponCode: (_coupon?.isValid ?? false) ? _coupon!.code : null,
              delivery: BookingDelivery(
                mode: _mode,
                addressId: _needsAddress ? _address!.id : null,
                itemDescription: _mode == ServiceMode.pickupDrop ? _itemController.text.trim() : null,
              ),
            ),
          );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Book Service')),
      body: BlocListener<BookingBloc, BookingState>(
        listener: (context, state) {
          if (state is BookingCreated) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Booking requested. The shop will confirm it shortly.'),
                backgroundColor: AppColors.success,
              ),
            );
            Navigator.pop(context);
          } else if (state is BookingError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          }
        },
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SummaryCard(
                  serviceName: widget.serviceName,
                  price: _price,
                  listPrice: _price == _listPrice ? null : _listPrice,
                ),
                const SizedBox(height: 24),
                if (widget.serviceModes.length > 1) ...[
                  const Text('How would you like it?', style: AppTextStyles.subtitle1),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final mode in widget.serviceModes)
                        ChoiceChip(
                          avatar: Icon(modeIcon(mode), size: 18),
                          label: Text(modeChoiceLabel(mode, mode == ServiceMode.atHome ? widget.homeVisitFee : mode == ServiceMode.pickupDrop ? widget.pickupFee : 0)),
                          selected: _mode == mode,
                          onSelected: (_) => setState(() => _mode = mode),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(modeExplanation(_mode), style: AppTextStyles.caption),
                  const SizedBox(height: 20),
                ],
                const Text('Schedule', style: AppTextStyles.subtitle1),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.calendar_today),
                        label: Text(
                          _selectedDate == null
                              ? 'Select Date'
                              : '${_selectedDate!.day}/${_selectedDate!.month}/${_selectedDate!.year}',
                        ),
                        onPressed: _pickDate,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.access_time),
                        label: Text(
                          _selectedTime == null
                              ? 'Select Time'
                              : _selectedTime!.format(context),
                        ),
                        onPressed: _pickTime,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                if (_needsAddress) ...[
                  Text(_mode == ServiceMode.pickupDrop ? 'Collect from' : 'Where should we come?', style: AppTextStyles.subtitle1),
                  const SizedBox(height: 12),
                  if (_saved.isEmpty)
                    Text(
                      'Add an address in Profile › Saved addresses first, then come back to book.',
                      style: AppTextStyles.body2.copyWith(color: AppColors.error),
                    )
                  else
                    DropdownButtonFormField<SavedAddress>(
                      initialValue: _address,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Saved address'),
                      items: [
                        for (final a in _saved) DropdownMenuItem(value: a, child: Text('${a.label}: ${a.oneLine}', overflow: TextOverflow.ellipsis)),
                      ],
                      onChanged: (a) => setState(() => _address = a),
                    ),
                  const SizedBox(height: 16),
                ],
                if (_mode == ServiceMode.pickupDrop) ...[
                  CustomTextField(
                    controller: _itemController,
                    label: 'What should we collect?',
                    hint: 'e.g. Honda Activa, brakes squeaking · Dell laptop, cracked screen',
                    maxLines: 2,
                    validator: Validators.required,
                  ),
                  const SizedBox(height: 16),
                ],
                CustomTextField(
                  controller: _notesController,
                  label: 'Notes (optional)',
                  hint: 'Any special instructions...',
                  maxLines: 2,
                ),
                const SizedBox(height: 16),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: CustomTextField(
                        controller: _couponController,
                        label: 'Coupon code (optional)',
                        hint: 'e.g. WELCOME10',
                      ),
                    ),
                    const SizedBox(width: 8),
                    Padding(
                      padding: const EdgeInsets.only(top: 28),
                      child: TextButton(
                        onPressed: _checkingCoupon ? null : _applyCoupon,
                        child: Text(_checkingCoupon ? 'Checking…' : 'Apply'),
                      ),
                    ),
                  ],
                ),
                if (_coupon != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      _coupon!.isValid
                          ? '${_coupon!.code}: ${_coupon!.discountPct.toStringAsFixed(_coupon!.discountPct % 1 == 0 ? 0 : 1)}% off'
                          : _coupon!.message,
                      style: AppTextStyles.caption.copyWith(color: _coupon!.isValid ? AppColors.success : AppColors.error),
                    ),
                  ),
                const SizedBox(height: 32),
                BlocBuilder<BookingBloc, BookingState>(
                  builder: (context, state) {
                    return CustomButton(
                      label: 'Confirm Booking',
                      onPressed: state is BookingLoading ? null : _onBook,
                      isLoading: state is BookingLoading,
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final String serviceName;
  final double price;
  final double? listPrice;

  const _SummaryCard({required this.serviceName, required this.price, this.listPrice});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primaryLight,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          const Icon(Icons.home_repair_service, color: AppColors.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(serviceName, style: AppTextStyles.subtitle1),
                Row(
                  children: [
                    Text('₹${price.toStringAsFixed(price % 1 == 0 ? 0 : 2)}', style: AppTextStyles.caption),
                    if (listPrice != null) ...[
                      const SizedBox(width: 6),
                      Text(
                        '₹${listPrice!.toStringAsFixed(listPrice! % 1 == 0 ? 0 : 2)}',
                        style: AppTextStyles.caption.copyWith(decoration: TextDecoration.lineThrough),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

IconData modeIcon(String mode) => switch (mode) {
      ServiceMode.atHome => Icons.home_outlined,
      ServiceMode.pickupDrop => Icons.local_shipping_outlined,
      _ => Icons.storefront_outlined,
    };

/// "Visit the shop", "At my place (+₹150)", "Pickup & drop (+₹99)".
String modeChoiceLabel(String mode, double fee) {
  final name = switch (mode) {
    ServiceMode.atHome => 'At my place',
    ServiceMode.pickupDrop => 'Pickup & drop',
    _ => 'Visit the shop',
  };
  return fee > 0 ? '$name (+₹${fee.toStringAsFixed(fee % 1 == 0 ? 0 : 2)})' : name;
}

String modeExplanation(String mode) => switch (mode) {
      ServiceMode.atHome => 'A professional comes to your address at the time you choose.',
      ServiceMode.pickupDrop => "We collect your item from your address, service it and bring it back. You'll be told at each step.",
      _ => 'You go to the shop at the time you choose. See "How to get there" on your booking.',
    };
