import 'package:flutter/material.dart';

import '../../../core/constants/support_constants.dart';
import '../../../core/di/injection_container.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/utils/format.dart';
import '../../booking/data/dispute_api.dart';
import '../../booking/domain/entities/booking.dart';
import '../../booking/domain/repositories/booking_repository.dart';
import '../../booking/presentation/pages/booking_history_page.dart';
import '../../booking/presentation/widgets/report_problem.dart';
import '../../directions/presentation/how_to_get_there_sheet.dart' show LinkOpener, openExternally;

/// A question and its answer, under a topic.
typedef Faq = ({String topic, String question, String answer});

List<Faq> faqs(AppLocalizations l) => [
      (topic: l.faqTopicBooking, question: l.faqBookQ, answer: l.faqBookA),
      (topic: l.faqTopicBooking, question: l.faqNoTimesQ, answer: l.faqNoTimesA),
      (topic: l.faqTopicCancel, question: l.faqCancelQ, answer: l.faqCancelA),
      (topic: l.faqTopicCancel, question: l.faqRescheduleQ, answer: l.faqRescheduleA),
      (topic: l.faqTopicPayments, question: l.faqPayQ, answer: l.faqPayA),
      (topic: l.faqTopicPayments, question: l.faqRefundQ, answer: l.faqRefundA),
      (topic: l.faqTopicPickup, question: l.faqPickupQ, answer: l.faqPickupA),
      (topic: l.faqTopicHome, question: l.faqHomeQ, answer: l.faqHomeA),
      (topic: l.faqTopicReviews, question: l.faqReviewQ, answer: l.faqReviewA),
      (topic: l.faqTopicReviews, question: l.faqProblemQ, answer: l.faqProblemA),
      (topic: l.faqTopicAccount, question: l.faqProfileQ, answer: l.faqProfileA),
      (topic: l.faqTopicAccount, question: l.faqSessionsQ, answer: l.faqSessionsA),
      (topic: l.faqTopicAccount, question: l.faqDeleteQ, answer: l.faqDeleteA),
    ];

/// Answers to common questions, and ways to reach the Alakh support team (the platform's email and
/// phone from [SupportContact], never a shop's), including reporting a problem with a booking.
class HelpSupportPage extends StatefulWidget {
  /// Opens mailto: and tel: links; replaceable in tests.
  final LinkOpener? open;
  final BookingRepository? bookings;
  final DisputeApi? disputeApi;

  const HelpSupportPage({super.key, this.open, this.bookings, this.disputeApi});

  @override
  State<HelpSupportPage> createState() => _HelpSupportPageState();
}

class _HelpSupportPageState extends State<HelpSupportPage> {
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _launch(Uri uri) async {
    final messenger = ScaffoldMessenger.of(context);
    final failed = context.l10n.helpCouldNotOpen(SupportContact.email, displayPhone(SupportContact.phone));
    bool opened;
    try {
      opened = await (widget.open ?? openExternally)(uri);
    } catch (_) {
      opened = false;
    }
    if (!opened) messenger.showSnackBar(SnackBar(content: Text(failed), backgroundColor: AppColors.error));
  }

  /// An email to support; about [booking] when given, with its number in the subject and body.
  Future<void> _email({Booking? booking}) {
    final l10n = context.l10n;
    final number = booking == null ? null : (booking.bookingNumber.isEmpty ? booking.id : booking.bookingNumber);
    final subject = number == null ? l10n.helpEmailSubject : l10n.helpEmailBookingSubject(number);
    final body = number == null ? '' : l10n.helpEmailBookingBody(number);
    // Encoded by hand: mail apps show a queryParameters "+" as a plus, not a space.
    return _launch(Uri.parse(
      'mailto:${SupportContact.email}?subject=${Uri.encodeComponent(subject)}&body=${Uri.encodeComponent(body)}',
    ));
  }

  Future<void> _call() => _launch(Uri(scheme: 'tel', path: SupportContact.phone));

  /// Picks the booking: one under way or finished goes to the app's problem report (support works
  /// from it); any other is emailed to support with its number filled in.
  Future<void> _report() async {
    final booking = await showModalBottomSheet<_Pick>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _BookingPicker(bookings: widget.bookings ?? sl<BookingRepository>()),
    );
    if (booking == null || !mounted) return;
    final b = booking.booking;
    if (b != null && b.canDispute) {
      await reportBookingProblem(context, b, api: widget.disputeApi);
    } else {
      await _email(booking: b);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final query = _search.text.trim().toLowerCase();
    final matches = faqs(l10n)
        .where((f) => query.isEmpty || '${f.topic} ${f.question} ${f.answer}'.toLowerCase().contains(query))
        .toList();
    final children = <Widget>[];
    String? topic;
    for (final f in matches) {
      if (f.topic != topic) {
        topic = f.topic;
        children.add(Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
          child: Semantics(header: true, child: Text(f.topic, style: AppTextStyles.subtitle2.themed(context))),
        ));
      }
      children.add(ExpansionTile(
        // Keyed by question so a filtered list doesn't hand one answer's open state to another.
        key: PageStorageKey(f.question),
        title: Text(f.question, style: AppTextStyles.body1),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        shape: const Border(),
        children: [Text(f.answer, style: AppTextStyles.body2.themed(context))],
      ));
    }
    return Scaffold(
      appBar: AppBar(title: Text(l10n.helpTitle)),
      body: ListView(
        padding: const EdgeInsets.only(bottom: 32),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: TextField(
              controller: _search,
              textInputAction: TextInputAction.search,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                hintText: l10n.helpSearchHint,
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _search.text.isEmpty
                    ? null
                    : IconButton(
                        tooltip: l10n.clearSearch,
                        icon: const Icon(Icons.clear),
                        onPressed: () => setState(_search.clear),
                      ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 20, 16, 0),
            child: Semantics(header: true, child: Text(l10n.helpFaqHeading, style: AppTextStyles.heading3)),
          ),
          ...children,
          if (matches.isEmpty)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(l10n.helpNoMatch(_search.text.trim()), style: AppTextStyles.body2.themed(context)),
            ),
          const SizedBox(height: 16),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
            child: Semantics(header: true, child: Text(l10n.helpContactHeading, style: AppTextStyles.heading3)),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text(l10n.helpContactNote, style: AppTextStyles.body2.themed(context)),
          ),
          const SizedBox(height: 8),
          _ContactTile(
            icon: Icons.report_outlined,
            title: l10n.helpReport,
            subtitle: l10n.helpReportSubtitle,
            onTap: _report,
          ),
          _ContactTile(icon: Icons.email_outlined, title: l10n.helpEmail, subtitle: SupportContact.email, onTap: _email),
          _ContactTile(
            icon: Icons.call_outlined,
            title: l10n.helpCall,
            subtitle: displayPhone(SupportContact.phone),
            onTap: _call,
          ),
        ],
      ),
    );
  }
}

class _ContactTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _ContactTile({required this.icon, required this.title, required this.subtitle, required this.onTap});

  @override
  Widget build(BuildContext context) => ListTile(
        leading: CircleAvatar(
          backgroundColor: context.colors.primaryContainer,
          child: Icon(icon, color: context.colors.primary),
        ),
        title: Text(title, style: AppTextStyles.body1),
        subtitle: Text(subtitle, style: AppTextStyles.caption.themed(context)),
        trailing: Icon(Icons.chevron_right, color: context.palette.muted),
        onTap: onTap,
      );
}

/// What the booking picker popped with: a booking, or none ("not listed", email support).
class _Pick {
  final Booking? booking;

  const _Pick(this.booking);
}

/// The customer's bookings, most recent first, to say which one the problem is about.
class _BookingPicker extends StatefulWidget {
  final BookingRepository bookings;

  const _BookingPicker({required this.bookings});

  @override
  State<_BookingPicker> createState() => _BookingPickerState();
}

class _BookingPickerState extends State<_BookingPicker> {
  List<Booking>? _bookings;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    widget.bookings.getUserBookings().then((result) {
      if (!mounted) return;
      result.fold(
        (_) => setState(() => _failed = true),
        (bookings) => setState(() => _bookings = [...bookings]..sort((a, b) => b.scheduledAt.compareTo(a.scheduledAt))),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final bookings = _bookings;
    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.7),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 4),
              child: Semantics(header: true, child: Text(l10n.helpPickBooking, style: AppTextStyles.heading3)),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 8),
              child: Text(l10n.helpPickBookingNote, style: AppTextStyles.caption.themed(context)),
            ),
            if (_failed)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                child: Text(l10n.helpBookingsFailed, style: AppTextStyles.body2.themed(context)),
              )
            else if (bookings == null)
              const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()))
            else
              Flexible(
                child: ListView(
                  shrinkWrap: true,
                  children: [
                    for (final b in bookings)
                      ListTile(
                        contentPadding: const EdgeInsets.symmetric(horizontal: 24),
                        title: Text(b.serviceName, style: AppTextStyles.body1),
                        subtitle: Text(
                          [
                            if (b.bookingNumber.isNotEmpty) l10n.bookingNumber(b.bookingNumber),
                            friendlyDateTime(b.scheduledAt, l10n: l10n),
                            bookingStatusLabel(l10n, b.status),
                          ].join(' · '),
                          style: AppTextStyles.caption.themed(context),
                        ),
                        onTap: () => Navigator.pop(context, _Pick(b)),
                      ),
                  ],
                ),
              ),
            ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 24),
              leading: Icon(Icons.email_outlined, color: context.colors.primary),
              title: Text(l10n.helpEmailInstead, style: AppTextStyles.body1),
              onTap: () => Navigator.pop(context, const _Pick(null)),
            ),
          ],
        ),
      ),
    );
  }
}
