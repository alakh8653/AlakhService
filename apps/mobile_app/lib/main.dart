import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'app/auth_gate.dart';
import 'core/di/injection_container.dart' as di;
import 'core/theme/app_theme.dart';
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
    // AuthBloc sits above MaterialApp so every pushed route can read it.
    return BlocProvider<AuthBloc>.value(
      value: di.sl<AuthBloc>()..add(const CheckAuthStatus()),
      child: MaterialApp(
        title: 'AlakhService',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        home: const AuthGate(),
      ),
    );
  }
}
