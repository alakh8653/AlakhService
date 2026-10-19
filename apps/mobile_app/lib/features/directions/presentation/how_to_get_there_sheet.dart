import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/network/api_errors.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/theme/app_text_styles.dart';
import '../data/shop_location_api.dart';
import '../data/travel_options.dart';

/// Opens a link in the app that handles it (Maps, Uber...). Replaceable in tests.
typedef LinkOpener = Future<bool> Function(Uri uri);

Future<bool> openExternally(Uri uri) => launchUrl(uri, mode: LaunchMode.externalApplication);

/// Shows the ways to reach [shopId]: own vehicle, public transport, walking, a cab.
Future<void> showHowToGetThere(BuildContext context, {required String shopId, ShopLocationApi? api, LinkOpener? open}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => HowToGetThereSheet(shopId: shopId, api: api, open: open),
  );
}

class HowToGetThereSheet extends StatefulWidget {
  final String shopId;
  final ShopLocationApi? api;
  final LinkOpener? open;

  const HowToGetThereSheet({super.key, required this.shopId, this.api, this.open});

  @override
  State<HowToGetThereSheet> createState() => _HowToGetThereSheetState();
}

class _HowToGetThereSheetState extends State<HowToGetThereSheet> {
  late final Future<Destination> _destination = (widget.api ?? sl<ShopLocationApi>()).destination(widget.shopId);

  static const _icons = {
    TravelMode.drive: Icons.directions_car,
    TravelMode.transit: Icons.directions_transit,
    TravelMode.walk: Icons.directions_walk,
    TravelMode.uber: Icons.local_taxi,
  };

  Future<void> _go(TravelOption option) async {
    final opened = await (widget.open ?? openExternally)(option.uri);
    if (!opened && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not open ${option.title.toLowerCase()}'), backgroundColor: AppColors.error),
      );
    }
  }

  Future<void> _copy(Destination d) async {
    await Clipboard.setData(ClipboardData(text: d.copyText));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Address copied. Paste it as the drop-off in Ola, Rapido or any ride app.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: FutureBuilder<Destination>(
          future: _destination,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return Padding(
                padding: const EdgeInsets.all(24),
                child: Text(apiErrorMessage(snapshot.error!), textAlign: TextAlign.center, style: AppTextStyles.body2.themed(context)),
              );
            }
            final d = snapshot.data;
            if (d == null) return const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator()));
            if (!d.hasCoordinates && d.address.trim().isEmpty) {
              return const Padding(
                padding: EdgeInsets.all(24),
                child: Text("This shop hasn't added its address yet. Contact them for directions.", textAlign: TextAlign.center),
              );
            }
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('How to get there', style: AppTextStyles.heading3),
                const SizedBox(height: 4),
                Text(d.name, style: AppTextStyles.subtitle1),
                if (d.address.isNotEmpty) Text(d.address, style: AppTextStyles.body2.themed(context)),
                const SizedBox(height: 8),
                for (final option in travelOptions(d))
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: CircleAvatar(
                      backgroundColor: context.colors.primaryContainer,
                      child: Icon(_icons[option.mode], color: context.colors.primary),
                    ),
                    title: Text(option.title),
                    subtitle: Text(option.subtitle),
                    trailing: const Icon(Icons.open_in_new, size: 18),
                    onTap: () => _go(option),
                  ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(
                    backgroundColor: context.colors.primaryContainer,
                    child: Icon(Icons.content_copy, color: context.colors.primary),
                  ),
                  title: const Text('Ola, Rapido or another ride app'),
                  subtitle: const Text('Copy the address to paste as your drop-off'),
                  onTap: () => _copy(d),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
