import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/service_types.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/service_card.dart';
import '../../../auth/domain/entities/user.dart';
import '../../../booking/data/booking_queue_api.dart';
import '../../../booking/domain/entities/booking.dart';
import '../../../booking/domain/repositories/booking_repository.dart';
import '../../../booking/presentation/pages/booking_history_page.dart';
import '../../../notifications/data/notifications_api.dart';
import '../../../services/domain/entities/service_entity.dart';
import '../../../services/domain/repositories/service_repository.dart';
import '../../../services/presentation/pages/service_detail_page.dart';
import '../../../../l10n/l10n.dart';
import 'all_services_page.dart';
import 'home_widgets.dart';

class HomePage extends StatefulWidget {
  final User user;
  final ValueChanged<String> onSearch;

  /// Shows the providers of a type of service.
  final ValueChanged<ServiceType>? onOpenType;

  /// Opens the notifications; the unread badge is refreshed when it completes.
  final Future<void> Function() onOpenNotifications;
  final VoidCallback onOpenBookings;
  final ServiceRepository? serviceRepository;
  final BookingRepository? bookingRepository;
  final NotificationsApi? notificationsApi;

  const HomePage({
    super.key,
    required this.user,
    required this.onSearch,
    this.onOpenType,
    required this.onOpenNotifications,
    required this.onOpenBookings,
    this.serviceRepository,
    this.bookingRepository,
    this.notificationsApi,
  });

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  void _openType(ServiceType type) {
    final open = widget.onOpenType;
    open != null ? open(type) : widget.onSearch(type.label(context.l10n));
  }

  late Future<List<ServiceEntity>> _popular;
  // The customer's soonest booking that is still ahead or under way, if any.
  Booking? _next;
  // Today's queue for the next booking, if it is at the shop today.
  BookingQueue? _nextQueue;
  int _unread = 0;

  NotificationsApi get _notifications => widget.notificationsApi ?? sl<NotificationsApi>();

  @override
  void initState() {
    super.initState();
    _popular = _loadPopular();
    _loadNext();
    _loadUnread();
  }

  Future<void> _loadUnread() async {
    try {
      final n = await _notifications.unreadCount();
      if (mounted) setState(() => _unread = n);
    } catch (_) {
      // The badge is a hint; the notifications screen shows the real list.
    }
  }

  String? _queueLine(AppLocalizations l10n) {
    final q = _nextQueue;
    if (q == null) return null;
    return switch (q.state) {
      'IN_PROGRESS' => l10n.liveQueueInProgress,
      'YOUR_TURN' => l10n.queueYourTurn,
      _ => l10n.liveQueueShort(
          q.position ?? 0,
          (q.waitMinutes ?? 0) > 0 ? l10n.liveQueueWait(l10n.queueWaitMinutes(q.waitMinutes!)) : l10n.queueYoureNext,
        ),
    };
  }

  Future<void> _loadNext() async {
    final result = await (widget.bookingRepository ?? sl<BookingRepository>()).getUserBookings();
    final now = DateTime.now();
    // Skip ones whose time went by unconfirmed: "Your next booking: Yesterday" would mislead.
    final upcoming = result
        .fold((_) => const <Booking>[], (bookings) => splitBookings(bookings).$1)
        .where((b) => !b.isOverdue(now))
        .toList();
    if (mounted) setState(() => _next = upcoming.isEmpty ? null : upcoming.first);
    final next = _next;
    final api = sl.isRegistered<BookingQueueApi>() ? sl<BookingQueueApi>() : null;
    if (next == null || api == null || next.serviceMode != 'AT_SHOP') return;
    try {
      final queue = await api.forBooking(next.id);
      if (mounted) setState(() => _nextQueue = queue.isLive ? queue : null);
    } catch (_) {
      // The card shows the booked time as before.
    }
  }

  Future<List<ServiceEntity>> _loadPopular() async {
    final result = await (widget.serviceRepository ?? sl<ServiceRepository>()).getServices(limit: 5);
    return result.fold((failure) => throw failure.message, (services) => services);
  }

  Future<void> _refresh() async {
    final popular = _loadPopular();
    setState(() => _popular = popular);
    await Future.wait<void>([popular.then((_) {}, onError: (_) {}), _loadNext(), _loadUnread()]);
  }

  Future<void> _openNotifications() async {
    await widget.onOpenNotifications();
    await _loadUnread();
  }

  String get _greeting {
    final hour = DateTime.now().hour;
    final l10n = context.l10n;
    if (hour < 12) return l10n.greetingMorning;
    if (hour < 17) return l10n.greetingAfternoon;
    return l10n.greetingEvening;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return SafeArea(
      child: RefreshIndicator(
        onRefresh: _refresh,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(),
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: SearchBarWidget(onSubmitted: widget.onSearch, hint: l10n.searchHint),
              ),
              const SizedBox(height: 20),
              if (_next != null)
                NextBookingCard(
                  serviceName: _next!.serviceName,
                  when: friendlyDateTime(_next!.scheduledAt, l10n: l10n),
                  status: bookingStatusLabel(l10n, _next!.status),
                  queueLine: _queueLine(l10n),
                  onTap: widget.onOpenBookings,
                )
              else
                BannerWidget(onTap: widget.onOpenBookings),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Semantics(header: true, child: Text(l10n.homeOurServices, style: AppTextStyles.heading3)),
              ),
              const SizedBox(height: 16),
              _buildCategoriesGrid(),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Semantics(header: true, child: Text(l10n.homePopular, style: AppTextStyles.heading3)),
              ),
              const SizedBox(height: 12),
              _buildPopular(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final firstName = widget.user.name.split(' ').first;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('$_greeting${firstName.isEmpty ? '' : ', $firstName'} 👋', style: AppTextStyles.body2.themed(context)),
                Text(context.l10n.homeFindService, style: AppTextStyles.heading2),
              ],
            ),
          ),
          IconButton(
            tooltip: _unread > 0 ? context.l10n.notificationsUnread(_unread) : context.l10n.notifications,
            onPressed: _openNotifications,
            icon: Badge(
              isLabelVisible: _unread > 0,
              label: Text(_unread > 99 ? '99+' : '$_unread'),
              child: Icon(Icons.notifications_outlined, color: context.colors.onSurface),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoriesGrid() {
    return LayoutBuilder(
      builder: (context, constraints) {
        // Four across on phones; large system text gets three so labels stay readable.
        final scale = MediaQuery.textScalerOf(context).scale(1);
        final columns = scale > 1.15 ? 3 : 4;
        return GridView.builder(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            mainAxisSpacing: 12,
            crossAxisSpacing: 8,
            mainAxisExtent: 88 + 18 * scale,
          ),
          itemCount: homeServiceTypeIds.length + 1,
          itemBuilder: (context, index) {
            if (index == homeServiceTypeIds.length) {
              return ServiceCategoryCard(
                key: const ValueKey('all-services'),
                icon: Icons.apps,
                label: context.l10n.allServices,
                onTap: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute(builder: (_) => AllServicesPage(onPick: _openType)),
                ),
              );
            }
            final type = serviceTypeById(homeServiceTypeIds[index])!;
            return ServiceCategoryCard(icon: type.icon, label: type.label(context.l10n), onTap: () => _openType(type));
          },
        );
      },
    );
  }

  Widget _buildPopular() {
    return FutureBuilder<List<ServiceEntity>>(
      future: _popular,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator()),
          );
        }
        final services = snapshot.data ?? const [];
        if (snapshot.hasError || services.isEmpty) {
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    snapshot.hasError ? context.l10n.homeLoadFailed : context.l10n.homeNoServices,
                    style: AppTextStyles.body2.themed(context),
                  ),
                ),
                if (snapshot.hasError) TextButton(onPressed: _refresh, child: Text(context.l10n.tryAgain)),
              ],
            ),
          );
        }
        return ListView.separated(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: services.length,
          separatorBuilder: (_, __) => const SizedBox(height: 12),
          itemBuilder: (context, i) => ServiceCard(
            service: services[i],
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => ServiceDetailPage(service: services[i])),
            ),
          ),
        );
      },
    );
  }
}
