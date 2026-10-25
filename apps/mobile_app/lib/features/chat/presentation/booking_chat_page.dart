import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/errors/exceptions.dart';
import '../../../core/network/api_errors.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/error_widget.dart';
import '../../../shared/widgets/loading_indicator.dart';
import '../data/chat_api.dart';

/// The chat between the customer and the shop on one booking. It checks for new messages every
/// [pollInterval] while open and marks the shop's messages read. Numbers are never shown: the server
/// hides contact details and calls go through the platform.
class BookingChatPage extends StatefulWidget {
  final String bookingId;

  /// Shown under the title, e.g. the service name.
  final String? subtitle;
  final ChatApi? chatApi;
  final Duration pollInterval;

  const BookingChatPage({
    super.key,
    required this.bookingId,
    this.subtitle,
    this.chatApi,
    this.pollInterval = const Duration(seconds: 10),
  });

  @override
  State<BookingChatPage> createState() => _BookingChatPageState();
}

class _BookingChatPageState extends State<BookingChatPage> {
  final _input = TextEditingController();

  // Oldest first, as they show top to bottom.
  List<ChatMessage> _messages = const [];
  ChatThread? _thread;
  // The oldest page loaded so far.
  int _oldestPage = 1;
  bool _hasOlder = false;
  bool _loadingOlder = false;
  bool _sending = false;
  bool _calling = false;
  String? _error;
  Timer? _poll;

  ChatApi get _api => widget.chatApi ?? sl<ChatApi>();

  @override
  void initState() {
    super.initState();
    _input.addListener(() => setState(() {}));
    _load();
    _poll = Timer.periodic(widget.pollInterval, (_) => _refresh());
  }

  @override
  void dispose() {
    _poll?.cancel();
    _input.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final thread = await _api.messages(widget.bookingId);
      if (!mounted) return;
      setState(() {
        _thread = thread;
        _messages = thread.items;
        _oldestPage = 1;
        _hasOlder = thread.hasOlder;
      });
      _markRead(thread);
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  /// Fetches the newest page and merges it in: new messages, and read receipts on ones shown.
  Future<void> _refresh() async {
    if (_thread == null) return;
    try {
      final thread = await _api.messages(widget.bookingId);
      if (!mounted) return;
      setState(() {
        _thread = thread;
        _messages = _merge(_messages, thread.items);
      });
      _markRead(thread);
    } catch (_) {
      // A missed poll is retried on the next tick.
    }
  }

  Future<void> _loadOlder() async {
    if (_loadingOlder) return;
    setState(() => _loadingOlder = true);
    try {
      final thread = await _api.messages(widget.bookingId, page: _oldestPage + 1);
      if (!mounted) return;
      setState(() {
        _oldestPage = thread.page;
        _hasOlder = thread.hasOlder;
        _messages = _merge(thread.items, _messages);
      });
    } catch (e) {
      if (mounted) _snack(apiErrorMessage(e), error: true);
    } finally {
      if (mounted) setState(() => _loadingOlder = false);
    }
  }

  /// Both lists, one entry per message (the later list's copy wins), oldest first.
  static List<ChatMessage> _merge(List<ChatMessage> a, List<ChatMessage> b) {
    final byId = <String, ChatMessage>{for (final m in a) m.id: m, for (final m in b) m.id: m};
    return byId.values.toList()..sort((x, y) => x.createdAt.compareTo(y.createdAt));
  }

  void _markRead(ChatThread thread) {
    if (thread.unread == 0) return;
    _api.markRead(widget.bookingId).catchError((Object _) {});
  }

  Future<void> _send() async {
    final body = _input.text.trim();
    if (body.isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      final message = await _api.send(widget.bookingId, body);
      if (!mounted) return;
      _input.clear();
      setState(() => _messages = _merge(_messages, [message]));
    } catch (e) {
      if (!mounted) return;
      _snack(apiErrorMessage(e), error: true);
      // A 409 means the chat closed meanwhile: show it read-only.
      if (e is ServerException && e.statusCode == 409) _refresh();
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _callShop() async {
    if (_calling) return;
    setState(() => _calling = true);
    try {
      final message = await _api.callShop(widget.bookingId);
      if (mounted) _snack(message.isEmpty ? context.l10n.chatCallPlaced : message);
    } catch (e) {
      if (mounted) _snack(apiErrorMessage(e), error: true);
    } finally {
      if (mounted) setState(() => _calling = false);
    }
  }

  void _snack(String text, {bool error = false}) => ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(text), backgroundColor: error ? AppColors.error : null),
      );

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final thread = _thread;
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.chatTitle),
            if (widget.subtitle != null)
              Text(widget.subtitle!, style: AppTextStyles.caption.copyWith(color: context.colors.onSurfaceVariant)),
          ],
        ),
        actions: [
          if (thread?.callingEnabled == true)
            TextButton.icon(
              onPressed: _calling ? null : _callShop,
              icon: const Icon(Icons.call_outlined, size: 18),
              label: Text(l10n.chatCallShop),
            ),
        ],
      ),
      body: _error != null && thread == null
          ? AppErrorWidget(message: _error!, onRetry: _load)
          : thread == null
              ? LoadingIndicator(message: l10n.chatLoading)
              : Column(
                  children: [
                    Expanded(child: _list(l10n)),
                    _composer(l10n, thread),
                  ],
                ),
    );
  }

  Widget _list(AppLocalizations l10n) {
    if (_messages.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text(l10n.chatEmpty, style: AppTextStyles.body2.themed(context), textAlign: TextAlign.center),
        ),
      );
    }
    // Reversed so the newest message sits at the bottom and the list starts there.
    final newestFirst = _messages.reversed.toList();
    return ListView.builder(
      reverse: true,
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      itemCount: newestFirst.length + (_hasOlder ? 1 : 0),
      itemBuilder: (context, i) {
        if (i == newestFirst.length) {
          return Center(
            child: TextButton(
              onPressed: _loadingOlder ? null : _loadOlder,
              child: Text(_loadingOlder ? l10n.loadingMore : l10n.chatLoadEarlier),
            ),
          );
        }
        return _Bubble(message: newestFirst[i]);
      },
    );
  }

  Widget _composer(AppLocalizations l10n, ChatThread thread) {
    final openUntil = thread.openUntil;
    if (!thread.canSend) {
      return SafeArea(
        top: false,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          color: context.colors.surfaceContainerHighest,
          child: Row(
            children: [
              Icon(Icons.lock_outline, size: 18, color: context.palette.muted),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  openUntil == null ? l10n.chatClosed : l10n.chatClosedSince(friendlyDateTime(openUntil, l10n: l10n)),
                  style: AppTextStyles.body2.themed(context),
                ),
              ),
            ],
          ),
        ),
      );
    }
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 4, 8, 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (openUntil != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 4, left: 4),
                child: Text(
                  l10n.chatOpenUntil(friendlyDateTime(openUntil, l10n: l10n)),
                  style: AppTextStyles.caption.copyWith(color: context.palette.muted),
                ),
              ),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    controller: _input,
                    minLines: 1,
                    maxLines: 4,
                    maxLength: 1000,
                    textCapitalization: TextCapitalization.sentences,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _send(),
                    decoration: InputDecoration(hintText: l10n.chatHint, counterText: ''),
                  ),
                ),
                IconButton(
                  tooltip: l10n.send,
                  onPressed: _sending || _input.text.trim().isEmpty ? null : _send,
                  icon: Icon(Icons.send, color: _input.text.trim().isEmpty ? null : context.colors.primary),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  final ChatMessage message;

  const _Bubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final mine = message.isMine;
    final background = mine ? context.colors.primary : context.colors.surfaceContainerHighest;
    final foreground = mine ? context.colors.onPrimary : context.colors.onSurface;
    final meta = foreground.withValues(alpha: 0.75);
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.78),
        child: Column(
          crossAxisAlignment: mine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            Container(
              margin: const EdgeInsets.only(top: 6),
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 6),
              decoration: BoxDecoration(
                color: background,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(mine ? 16 : 4),
                  bottomRight: Radius.circular(mine ? 4 : 16),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (!mine)
                    Text(
                      message.senderName.isEmpty ? l10n.chatShop : message.senderName,
                      style: AppTextStyles.caption.copyWith(color: context.colors.primary, fontWeight: FontWeight.w600),
                    ),
                  Text(message.body, style: AppTextStyles.body1.copyWith(color: foreground)),
                  const SizedBox(height: 2),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(clockTime(message.createdAt), style: AppTextStyles.caption.copyWith(color: meta, fontSize: 11)),
                      if (mine) ...[
                        const SizedBox(width: 4),
                        Semantics(
                          label: message.isRead ? l10n.chatRead : l10n.chatSent,
                          child: Tooltip(
                            message: message.isRead ? l10n.chatRead : l10n.chatSent,
                            child: Icon(message.isRead ? Icons.done_all : Icons.done, size: 14, color: meta),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
            if (message.flagged)
              Padding(
                padding: const EdgeInsets.only(top: 2, left: 4, right: 4),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.shield_outlined, size: 12, color: context.palette.muted),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(
                        l10n.chatFlaggedHint,
                        style: AppTextStyles.caption.copyWith(color: context.palette.muted, fontSize: 11),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
