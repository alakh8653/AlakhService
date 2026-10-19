import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Phone, RefreshCw, Send, ShieldCheck } from 'lucide-react';
import {
  MAX_MESSAGE_LENGTH,
  callCustomer,
  getMessages,
  markRead,
  sendMessage,
  type ChatPage,
} from '../services/chatService';
import { apiErrorMessage, formatDayTime } from '../services/format';

// New messages show up this often while the chat is open.
const REFRESH_MS = 15_000;

/**
 * The booking's chat with its customer. Contact details are never exchanged: the server hides phone
 * numbers, emails and UPI handles, and calls (when enabled) go through the platform's number.
 */
export default function BookingChat({ bookingId, customerName }: { bookingId: string; customerName: string }) {
  const [chat, setChat] = useState<ChatPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [calling, setCalling] = useState(false);
  const listRef = useRef<HTMLOListElement>(null);

  const load = useCallback(async () => {
    try {
      const page = await getMessages(bookingId);
      setChat(page);
      setError(null);
      if (page.unread > 0) await markRead(bookingId).catch(() => undefined);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not load messages'));
    }
  }, [bookingId]);

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    listRef.current?.scrollTo?.({ top: listRef.current.scrollHeight });
  }, [chat?.messages.length]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    setSending(true);
    setNotice(null);
    try {
      const message = await sendMessage(bookingId, draft);
      setChat((c) => (c ? { ...c, messages: [...c.messages, message], total: c.total + 1 } : c));
      setDraft('');
      if (message.flagged) setNotice('Contact details were hidden. Please keep talking here, so both sides stay protected.');
    } catch (err) {
      setNotice(apiErrorMessage(err, 'Could not send the message'));
    } finally {
      setSending(false);
    }
  };

  const call = async () => {
    setCalling(true);
    setNotice(null);
    try {
      setNotice(await callCustomer(bookingId));
    } catch (err) {
      setNotice(apiErrorMessage(err, 'Could not place the call'));
    } finally {
      setCalling(false);
    }
  };

  return (
    <section aria-label={`Chat with ${customerName}`} className="border-t border-gray-100 pt-3 mt-2 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-gray-500 flex items-center gap-1">
          <ShieldCheck size={14} className="text-green-600" aria-hidden />
          Numbers and emails stay private on both sides.
        </p>
        <div className="flex items-center gap-1">
          {chat?.callingEnabled && (
            <button
              type="button"
              onClick={() => void call()}
              disabled={calling}
              className="flex items-center gap-1 text-xs text-indigo-700 border border-indigo-200 rounded-lg px-2 py-1 hover:bg-indigo-50 disabled:opacity-50"
            >
              <Phone size={12} aria-hidden /> {calling ? 'Calling…' : 'Call customer'}
            </button>
          )}
          <button
            type="button"
            onClick={() => void load()}
            aria-label="Refresh messages"
            className="p-1 text-gray-500 hover:text-gray-800"
          >
            <RefreshCw size={14} aria-hidden />
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {chat && chat.messages.length === 0 && <p className="text-sm text-gray-500">No messages yet.</p>}
      {chat && chat.messages.length > 0 && (
        <ol ref={listRef} aria-label="Messages" className="max-h-64 overflow-y-auto space-y-2 pr-1">
          {chat.messages.map((m) => (
            <li key={m.id} className={`flex ${m.isMine ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                  m.isMine ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-900'
                }`}
              >
                {!m.isMine && <p className="text-xs font-semibold mb-0.5">{m.senderName}</p>}
                <p className="whitespace-pre-wrap break-words">{m.body}</p>
                <p className={`text-[11px] mt-0.5 ${m.isMine ? 'text-indigo-100' : 'text-gray-500'}`}>
                  {formatDayTime(m.createdAt)}
                  {m.isMine && (m.readAt ? ' · Read' : ' · Sent')}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}

      {notice && (
        <p role="status" className="text-xs text-amber-700">
          {notice}
        </p>
      )}

      {chat && !chat.canSend ? (
        <p className="text-xs text-gray-500">This booking is closed, so its chat is read-only.</p>
      ) : (
        <form onSubmit={(e) => void send(e)} className="flex items-end gap-2">
          <textarea
            aria-label={`Message ${customerName}`}
            value={draft}
            maxLength={MAX_MESSAGE_LENGTH}
            rows={1}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Write a message…"
            className="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-2 resize-none"
          />
          <button
            type="submit"
            disabled={sending || !draft.trim() || !chat}
            aria-label="Send message"
            className="bg-indigo-600 text-white rounded-lg p-2 hover:bg-indigo-700 disabled:opacity-50"
          >
            <Send size={16} aria-hidden />
          </button>
        </form>
      )}
      {chat?.openUntil && chat.canSend && (
        <p className="text-[11px] text-gray-500">You can write until {formatDayTime(chat.openUntil)}.</p>
      )}
    </section>
  );
}
