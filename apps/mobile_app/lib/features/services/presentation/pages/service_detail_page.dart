import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_state.dart';
import '../../../booking/presentation/bloc/booking_bloc.dart';
import '../../../booking/presentation/pages/booking_page.dart';
import '../../../directions/data/shop_location_api.dart';
import '../../../directions/data/travel_options.dart';
import '../../../directions/presentation/how_to_get_there_sheet.dart';
import '../../../queue/data/queue_api.dart';
import '../../../queue/presentation/pages/queue_status_page.dart';
import '../../../reviews/data/reviews_api.dart';
import '../../../reviews/presentation/reviews_widgets.dart';
import '../../../shops/data/shop_hours_api.dart';
import '../../domain/entities/service_entity.dart';

class ServiceDetailPage extends StatefulWidget {
  final ServiceEntity service;
  final ShopLocationApi? shopApi;
  final QueueApi? queueApi;
  final ReviewsApi? reviewsApi;
  final ShopHoursApi? hoursApi;

  /// The current time (replaceable in tests).
  final DateTime Function() clock;

  const ServiceDetailPage({
    super.key,
    required this.service,
    this.shopApi,
    this.queueApi,
    this.reviewsApi,
    this.hoursApi,
    this.clock = DateTime.now,
  });

  @override
  State<ServiceDetailPage> createState() => _ServiceDetailPageState();
}

class _ServiceDetailPageState extends State<ServiceDetailPage> {
  late final QueueApi _queueApi = widget.queueApi ?? sl<QueueApi>();
  String? _openQueueId;
  bool _joining = false;
  // Who provides it: the shop's name and area, so the customer knows where they are booking.
  Destination? _shop;
  // What customers say about the shop, for choosing it.
  late final ReviewsApi? _reviewsApi = service.shopId == null ? null : widget.reviewsApi ?? sl<ReviewsApi>();
  RatingSummary? _summary;
  // "Open now · closes 8 PM", once the shop's hours are in (none for a shop that hasn't published them).
  ShopHours? _hours;

  ServiceEntity get service => widget.service;

  @override
  void initState() {
    super.initState();
    // Walk-in queue, if the shop runs one for this service.
    _queueApi.openQueueFor(service.id).then((id) {
      if (mounted) setState(() => _openQueueId = id);
    }).catchError((_) {});
    final shopId = service.shopId;
    if (shopId != null) {
      (widget.shopApi ?? sl<ShopLocationApi>()).destination(shopId).then((shop) {
        if (mounted) setState(() => _shop = shop);
      }).catchError((Object _) {});
      _reviewsApi!.summary(shopId).then((summary) {
        if (mounted) setState(() => _summary = summary);
      }).catchError((Object _) {});
      // Only a line of extra information: if it can't be had, the page goes on without it.
      Future(() => (widget.hoursApi ?? sl<ShopHoursApi>()).forShop(shopId)).then((hours) {
        if (mounted) setState(() => _hours = hours);
      }).catchError((Object _) {});
    }
  }

  void _book() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => BlocProvider<BookingBloc>(
          create: (_) => sl<BookingBloc>(),
          child: BookingPage(
            serviceId: service.id,
            serviceName: service.name,
            servicePrice: service.basePrice,
            serviceModes: service.serviceModes,
            homeVisitFee: service.homeVisitFee,
            pickupFee: service.pickupFee,
          ),
        ),
      ),
    );
  }

  Future<void> _joinQueue() async {
    final auth = context.read<AuthBloc>().state;
    final queueId = _openQueueId;
    if (auth is! Authenticated || queueId == null || _joining) return;
    setState(() => _joining = true);
    try {
      final ticket = await _queueApi.join(queueId: queueId, serviceId: service.id, customerId: auth.user.id);
      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => QueueStatusPage(ticket: ticket, customerId: auth.user.id, serviceName: service.name),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }

  Widget _placeholder() => Container(
        color: AppColors.primaryLight,
        child: const Icon(Icons.home_repair_service, size: 80, color: AppColors.primary),
      );

  @override
  Widget build(BuildContext context) {
    final shop = _shop;
    final atShop = service.serviceModes.contains(ServiceMode.atShop);
    final rating = _summary?.average ?? service.rating;
    final reviewCount = _summary?.count ?? service.reviewCount;
    return Scaffold(
      bottomNavigationBar: Material(
        color: AppColors.surface,
        elevation: 8,
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (!service.isAvailable)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      "This service isn't taking bookings right now.",
                      style: AppTextStyles.caption.copyWith(color: AppColors.error),
                    ),
                  ),
                Row(
                  children: [
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('From', style: AppTextStyles.caption),
                        Text(rupees(service.basePrice), style: AppTextStyles.heading3.copyWith(color: AppColors.primary)),
                      ],
                    ),
                    const SizedBox(width: 16),
                    Expanded(child: CustomButton(label: 'Book Now', onPressed: service.isAvailable ? _book : null)),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 200,
            pinned: true,
            flexibleSpace: FlexibleSpaceBar(
              background: service.imageUrl != null
                  ? Image.network(service.imageUrl!, fit: BoxFit.cover, errorBuilder: (_, __, ___) => _placeholder())
                  : _placeholder(),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Semantics(header: true, child: Text(service.name, style: AppTextStyles.heading2)),
                  if (shop != null) ...[
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        const Icon(Icons.storefront_outlined, size: 16, color: AppColors.textSecondary),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            [shop.name, if (shop.address.isNotEmpty) shop.address].join(' · '),
                            style: AppTextStyles.body2,
                          ),
                        ),
                      ],
                    ),
                  ],
                  if (_hours case final hours?)
                    if (openingSummary(hours, widget.clock()) case final open?) ...[
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(Icons.schedule, size: 16, color: open.open ? AppColors.success : AppColors.textSecondary),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            open.text,
                            style: AppTextStyles.body2.copyWith(
                              color: open.open ? AppColors.success : AppColors.textSecondary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 16,
                    runSpacing: 4,
                    children: [
                      if (service.durationMinutes != null && service.durationMinutes! > 0)
                        _Fact(icon: Icons.schedule, text: 'About ${service.durationMinutes} min'),
                      if (reviewCount > 0)
                        Semantics(
                          label: 'Rated ${rating.toStringAsFixed(1)} out of 5 from ${reviewsCount(reviewCount)}',
                          excludeSemantics: true,
                          child: _Fact(
                            icon: Icons.star,
                            iconColor: AppColors.starFilled,
                            text: '${rating.toStringAsFixed(1)} (${reviewsCount(reviewCount)})',
                          ),
                        )
                      else
                        const _Fact(icon: Icons.star_border, text: 'New, no reviews yet'),
                    ],
                  ),
                  const SizedBox(height: 24),
                  const Text('How you can get it', style: AppTextStyles.subtitle1),
                  const SizedBox(height: 8),
                  for (final mode in service.serviceModes)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      leading: CircleAvatar(
                        backgroundColor: AppColors.primaryLight,
                        child: Icon(modeIcon(mode), color: AppColors.primary, size: 20),
                      ),
                      title: Text(
                        switch (mode) {
                          ServiceMode.atHome => 'At your place',
                          ServiceMode.pickupDrop => 'Pickup & drop',
                          _ => 'At the shop',
                        },
                        style: AppTextStyles.body1,
                      ),
                      subtitle: Text(modeExplanation(mode), style: AppTextStyles.caption),
                      trailing: service.feeFor(mode) > 0
                          ? Text('+${rupees(service.feeFor(mode))}', style: AppTextStyles.subtitle2)
                          : null,
                    ),
                  const SizedBox(height: 16),
                  const Text('About this service', style: AppTextStyles.subtitle1),
                  const SizedBox(height: 8),
                  Text(
                    service.description.isEmpty ? 'The shop has not added a description yet.' : service.description,
                    style: AppTextStyles.body2,
                  ),
                  if (service.tags.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      children: service.tags
                          .map((t) => Chip(label: Text(t, style: AppTextStyles.caption), backgroundColor: AppColors.primaryLight))
                          .toList(),
                    ),
                  ],
                  if (_reviewsApi != null && _summary != null) ...[
                    const SizedBox(height: 24),
                    ReviewsSection(shopId: service.shopId!, api: _reviewsApi!, summary: _summary, shopName: shop?.name),
                  ],
                  const SizedBox(height: 24),
                  if (_openQueueId != null) ...[
                    CustomButton(
                      label: 'Walk in now: join the queue',
                      variant: ButtonVariant.outlined,
                      leadingIcon: Icons.people_outline,
                      isLoading: _joining,
                      onPressed: _joining ? null : _joinQueue,
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      "No appointment needed: we'll tell you your place and when it's your turn.",
                      style: AppTextStyles.caption,
                    ),
                    const SizedBox(height: 12),
                  ],
                  if (service.shopId != null && atShop)
                    Center(
                      child: TextButton.icon(
                        onPressed: () => showHowToGetThere(context, shopId: service.shopId!),
                        icon: const Icon(Icons.directions),
                        label: const Text('How to get there'),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Fact extends StatelessWidget {
  final IconData icon;
  final String text;
  final Color iconColor;

  const _Fact({required this.icon, required this.text, this.iconColor = AppColors.textSecondary});

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: iconColor),
          const SizedBox(width: 4),
          Flexible(child: Text(text, style: AppTextStyles.caption)),
        ],
      );
}
