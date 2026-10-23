import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'app/app_view.dart';
import 'app/auth_gate.dart';
import 'app/offline_banner.dart';
import 'core/di/injection_container.dart' as di;
import 'core/settings/app_settings.dart';
import 'features/auth/presentation/bloc/auth_bloc.dart';
import 'features/auth/presentation/bloc/auth_event.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await di.init();
  runApp(AlakhServiceApp(online: onlineStatus(di.sl<Connectivity>())));
}

class AlakhServiceApp extends StatelessWidget {
  /// Whether the device is online, for the offline strip.
  final Stream<bool>? online;

  const AlakhServiceApp({super.key, this.online});

  @override
  Widget build(BuildContext context) {
    // AuthBloc and the display settings sit above MaterialApp so every pushed route can read them.
    return MultiBlocProvider(
      providers: [
        BlocProvider<AuthBloc>.value(value: di.sl<AuthBloc>()..add(const CheckAuthStatus())),
        BlocProvider<SettingsCubit>.value(value: di.sl<SettingsCubit>()),
      ],
      child: AppView(home: const AuthGate(), online: online),
    );
  }
}
