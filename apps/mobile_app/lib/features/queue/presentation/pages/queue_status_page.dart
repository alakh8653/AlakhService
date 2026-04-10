import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';

class QueueStatusPage extends StatefulWidget {
  final String bookingId;

  const QueueStatusPage({super.key, required this.bookingId});

  @override
  State<QueueStatusPage> createState() => _QueueStatusPageState();
}

class _QueueStatusPageState extends State<QueueStatusPage>
    with TickerProviderStateMixin {
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  // Simulated queue data
  final int _queuePosition = 3;
  final int _estimatedMinutes = 12;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.8, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Queue Status')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            const SizedBox(height: 24),
            ScaleTransition(
              scale: _pulseAnimation,
              child: Container(
                width: 160,
                height: 160,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: AppColors.primaryLight,
                  border: Border.all(color: AppColors.primary, width: 3),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      '#$_queuePosition',
                      style: AppTextStyles.heading1
                          .copyWith(color: AppColors.primary),
                    ),
                    Text('Your Position', style: AppTextStyles.caption),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),
            Text('Estimated Wait Time', style: AppTextStyles.subtitle1),
            const SizedBox(height: 8),
            Text(
              '$_estimatedMinutes min',
              style: AppTextStyles.heading2.copyWith(color: AppColors.accent),
            ),
            const SizedBox(height: 32),
            const Divider(),
            const SizedBox(height: 24),
            _QueueStep(
              step: 1,
              label: 'Booking Confirmed',
              isDone: true,
            ),
            _QueueStep(
              step: 2,
              label: 'Provider Assigned',
              isDone: true,
            ),
            _QueueStep(
              step: 3,
              label: 'Provider En Route',
              isActive: true,
            ),
            _QueueStep(
              step: 4,
              label: 'Service In Progress',
            ),
            _QueueStep(
              step: 5,
              label: 'Completed',
              isLast: true,
            ),
          ],
        ),
      ),
    );
  }
}

class _QueueStep extends StatelessWidget {
  final int step;
  final String label;
  final bool isDone;
  final bool isActive;
  final bool isLast;

  const _QueueStep({
    required this.step,
    required this.label,
    this.isDone = false,
    this.isActive = false,
    this.isLast = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = isDone
        ? AppColors.success
        : isActive
            ? AppColors.primary
            : AppColors.textDisabled;

    return Row(
      children: [
        Column(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: color.withOpacity(isDone || isActive ? 1 : 0.2),
              ),
              child: Icon(
                isDone ? Icons.check : Icons.circle,
                color: isDone || isActive ? Colors.white : AppColors.textDisabled,
                size: 16,
              ),
            ),
            if (!isLast)
              Container(width: 2, height: 32, color: color.withOpacity(0.3)),
          ],
        ),
        const SizedBox(width: 12),
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Text(
            label,
            style: AppTextStyles.body2.copyWith(
              color: color,
              fontWeight: isActive ? FontWeight.w600 : null,
            ),
          ),
        ),
      ],
    );
  }
}
