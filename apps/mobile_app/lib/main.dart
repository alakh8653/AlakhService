import 'package:app_links/app_links.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'app/app_keys.dart';
import 'app/app_view.dart';
import 'app/auth_gate.dart';
import 'app/link_handler.dart';
import 'app/offline_banner.dart';
import 'core/di/injection_container.dart' as di;
import 'core/settings/app_settings.dart';
import 'features/auth/presentation/bloc/auth_bloc.dart';
import 'features/auth/presentation/bloc/auth_event.dart';
import 'features/push/push_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Null without Firebase config (google-services.json / GoogleService-Info.plist): no push then.
  final push = await initFirebasePush();
  await di.init(push: push);
  runApp(AlakhServiceApp(
    online: onlineStatus(di.sl<Connectivity>()),
    links: await appLinkStream(),
    push: di.sl<PushService>(),
  ));
}

/// App links as they arrive, the one that launched the app included; null where the platform has no
/// app-links plugin (desktop test runs).
Future<Stream<Uri>?> appLinkStream() async {
  final links = AppLinks();
  try {
    await links.getLatestLink();
  } catch (_) {
    return null;
  }
  return links.uriLinkStream;
}

class AlakhServiceApp extends StatelessWidget {
  /// Whether the device is online, for the offline strip.
  final Stream<bool>? online;

  /// App links (https://{domain}/b/{id}, /reset-password?token=) and push notifications.
  final Stream<Uri>? links;
  final PushService? push;

  const AlakhServiceApp({super.key, this.online, this.links, this.push});

  @override
  Widget build(BuildContext context) {
    // AuthBloc and the display settings sit above MaterialApp so every pushed route can read them.
    return MultiBlocProvider(
      providers: [
        BlocProvider<AuthBloc>.value(value: di.sl<AuthBloc>()..add(const CheckAuthStatus())),
        BlocProvider<SettingsCubit>.value(value: di.sl<SettingsCubit>()),
      ],
      child: LinkHandler(
        navigatorKey: appNavigatorKey,
        messengerKey: appMessengerKey,
        links: links,
        push: push,
        child: AppView(
          home: const AuthGate(),
          online: online,
          navigatorKey: appNavigatorKey,
          messengerKey: appMessengerKey,
        ),
      ),
    );
  }
}
