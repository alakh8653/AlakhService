import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../features/auth/presentation/bloc/auth_bloc.dart';
import '../features/auth/presentation/bloc/auth_state.dart';
import '../features/auth/presentation/pages/reset_password_link_page.dart';
import '../features/booking/presentation/pages/booking_details_page.dart';
import '../features/chat/presentation/booking_chat_page.dart';
import '../features/push/push_service.dart';
import '../l10n/l10n.dart';
import 'app_links.dart';

/// The screen a target opens.
typedef TargetPageBuilder = Widget Function(AppTarget target);

Widget defaultTargetPage(AppTarget target) => switch (target) {
      BookingTarget(chat: true) => BookingChatPage(bookingId: target.bookingId),
      BookingTarget() => BookingDetailsPage(bookingId: target.bookingId),
      ResetPasswordTarget() => ResetPasswordLinkPage(token: target.token),
    };

/// Opens app links and tapped notifications, and keeps push registered for whoever is signed in.
/// A booking link that arrives before sign-in opens once the customer has signed in. Sits under
/// the [AuthBloc] and above the MaterialApp whose [navigatorKey] and [messengerKey] it uses.
class LinkHandler extends StatefulWidget {
  final Widget child;
  final GlobalKey<NavigatorState> navigatorKey;
  final GlobalKey<ScaffoldMessengerState> messengerKey;

  /// App links while running, and the one that launched the app.
  final Stream<Uri>? links;
  final Future<Uri?> Function()? initialLink;
  final PushService? push;
  final TargetPageBuilder pageFor;

  const LinkHandler({
    super.key,
    required this.child,
    required this.navigatorKey,
    required this.messengerKey,
    this.links,
    this.initialLink,
    this.push,
    this.pageFor = defaultTargetPage,
  });

  @override
  State<LinkHandler> createState() => _LinkHandlerState();
}

class _LinkHandlerState extends State<LinkHandler> {
  final List<StreamSubscription<Object?>> _subscriptions = [];
  AppTarget? _pending;
  bool _signedIn = false;

  @override
  void initState() {
    super.initState();
    final auth = context.read<AuthBloc>();
    _subscriptions.add(auth.stream.listen(_onAuth));
    _onAuth(auth.state);

    final links = widget.links;
    if (links != null) _subscriptions.add(links.listen(_onLink));
    widget.initialLink?.call().then((uri) {
      if (uri != null) _onLink(uri);
    }).catchError((Object _) {});

    final push = widget.push;
    if (push != null) {
      _subscriptions
        ..add(push.taps.listen(open))
        ..add(push.foreground.listen(_onForeground));
      push.start().then((_) {
        final launch = push.takeLaunchTarget();
        if (launch != null) open(launch);
      });
    }
  }

  @override
  void dispose() {
    for (final s in _subscriptions) {
      s.cancel();
    }
    super.dispose();
  }

  void _onAuth(AuthState state) {
    if (state is Authenticated && !_signedIn) {
      _signedIn = true;
      widget.push?.onSignedIn(state.user.id);
      // After the sign-in gate has reset the screens.
      final pending = _pending;
      _pending = null;
      if (pending != null) WidgetsBinding.instance.endOfFrame.then((_) => open(pending));
    } else if (state is Unauthenticated && _signedIn) {
      _signedIn = false;
      widget.push?.onSignedOut();
    }
  }

  void _onLink(Uri uri) {
    final target = parseAppLink(uri);
    if (target != null) open(target);
  }

  /// Shows [target]; a booking waits for sign-in.
  void open(AppTarget target) {
    if (target is BookingTarget && !_signedIn) {
      _pending = target;
      return;
    }
    widget.navigatorKey.currentState?.push(MaterialPageRoute<void>(builder: (_) => widget.pageFor(target)));
  }

  void _onForeground(PushMessage message) {
    final messenger = widget.messengerKey.currentState;
    final text = [message.title, message.body].whereType<String>().where((s) => s.isNotEmpty).join('\n');
    if (messenger == null || text.isEmpty) return;
    final target = pushTarget(message.data);
    final l10n = currentL10n;
    messenger.showSnackBar(SnackBar(
      content: Text(text),
      behavior: SnackBarBehavior.floating,
      action: target == null ? null : SnackBarAction(label: l10n.view, onPressed: () => open(target)),
    ));
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
