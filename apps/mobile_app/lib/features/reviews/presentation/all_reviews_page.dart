import 'package:flutter/material.dart';

import '../../../core/network/api_errors.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/error_widget.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../data/reviews_api.dart';
import 'reviews_widgets.dart';
import '../../../l10n/l10n.dart';

/// Every review of a shop, newest first, with chips to show only one star level.
class AllReviewsPage extends StatefulWidget {
  final String shopId;
  final String? shopName;
  final ReviewsApi api;
  final int pageSize;

  const AllReviewsPage({super.key, required this.shopId, required this.api, this.shopName, this.pageSize = 10});

  @override
  State<AllReviewsPage> createState() => _AllReviewsPageState();
}

class _AllReviewsPageState extends State<AllReviewsPage> {
  RatingSummary? _summary;
  final List<Review> _reviews = [];
  int _total = 0;
  int? _stars;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    widget.api.summary(widget.shopId).then((s) {
      if (mounted) setState(() => _summary = s);
    }).catchError((Object _) {});
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final stars = _stars;
    try {
      final page = await widget.api.reviews(widget.shopId, limit: widget.pageSize, rating: stars);
      if (!mounted || stars != _stars) return; // a newer filter was picked meanwhile
      setState(() {
        _reviews
          ..clear()
          ..addAll(page.items);
        _total = page.total;
        _loading = false;
      });
    } catch (e) {
      if (mounted && stars == _stars) {
        setState(() {
          _error = apiErrorMessage(e);
          _loading = false;
        });
      }
    }
  }

  Future<void> _more() async {
    setState(() => _loadingMore = true);
    final stars = _stars;
    try {
      final page = await widget.api.reviews(widget.shopId, skip: _reviews.length, limit: widget.pageSize, rating: stars);
      if (!mounted || stars != _stars) return;
      setState(() {
        final seen = _reviews.map((r) => r.id).toSet();
        _reviews.addAll(page.items.where((r) => !seen.contains(r.id)));
        _total = page.total;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _pick(int? stars) {
    if (stars == _stars) return;
    setState(() => _stars = stars);
    _load();
  }

  Widget _chips() => SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Row(
          children: [
            for (final stars in <int?>[null, 5, 4, 3, 2, 1])
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: Semantics(
                  label: stars == null ? context.l10n.allRatings : context.l10n.starsOnly(stars),
                  excludeSemantics: true,
                  selected: _stars == stars,
                  button: true,
                  child: ChoiceChip(
                    label: Text(stars == null ? context.l10n.allFilter : '$stars ★'),
                    selected: _stars == stars,
                    onSelected: (_) => _pick(stars),
                  ),
                ),
              ),
          ],
        ),
      );

  Widget _body() {
    if (_loading) return LoadingIndicator(message: context.l10n.loadingReviews);
    if (_error != null) return AppErrorWidget(message: _error!, onRetry: _load);
    if (_reviews.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(32),
        child: Text(
          _stars == null ? context.l10n.noReviewsYet : context.l10n.noStarReviews(_stars!),
          style: AppTextStyles.body2.themed(context),
          textAlign: TextAlign.center,
        ),
      );
    }
    return Column(
      children: [
        for (final r in _reviews) ...[
          Padding(padding: const EdgeInsets.symmetric(horizontal: 16), child: ReviewTile(review: r)),
          const Divider(height: 1, indent: 16, endIndent: 16),
        ],
        if (_reviews.length < _total)
          Padding(
            padding: const EdgeInsets.all(16),
            child: OutlinedButton(
              onPressed: _loadingMore ? null : _more,
              child: Text(_loadingMore ? context.l10n.loadingMore : context.l10n.showMoreReviews),
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final summary = _summary;
    return Scaffold(
      appBar: AppBar(title: Text(widget.shopName == null ? context.l10n.reviewsTitle : context.l10n.reviewsOf(widget.shopName!))),
      body: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          if (summary != null)
            Padding(padding: const EdgeInsets.fromLTRB(16, 16, 16, 8), child: RatingSummaryView(summary: summary)),
          const SizedBox(height: 8),
          _chips(),
          const SizedBox(height: 8),
          _body(),
        ],
      ),
    );
  }
}
