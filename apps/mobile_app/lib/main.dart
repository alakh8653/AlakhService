import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'app/app_view.dart';
import 'app/auth_gate.dart';
import 'core/di/injection_container.dart' as di;
import 'core/settings/app_settings.dart';
import 'features/auth/presentation/bloc/auth_bloc.dart';
import 'features/auth/presentation/bloc/auth_event.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await di.init();
  runApp(const AlakhServiceApp());
}

class AlakhServiceApp extends StatelessWidget {
  const AlakhServiceApp({super.key});

  @override
  Widget build(BuildContext context) {
    // AuthBloc and the display settings sit above MaterialApp so every pushed route can read them.
    return MultiBlocProvider(
      providers: [
        BlocProvider<AuthBloc>.value(value: di.sl<AuthBloc>()..add(const CheckAuthStatus())),
        BlocProvider<SettingsCubit>.value(value: di.sl<SettingsCubit>()),
      ],
      child: const AppView(home: AuthGate()),
    );
  }
}
