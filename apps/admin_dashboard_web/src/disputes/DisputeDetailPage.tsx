import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { format } from 'date-fns';
import { ArrowLeft, FileText } from 'lucide-react';
import { currentAdminId } from '../apiClient';
import {
  addDisputeMessage,
  escalateDispute,
  formatStatus,
  getDisputeById,
  getDisputeMessages,
  resolveDispute,
  startReview,
  STATUS_COLORS,
  type Dispute,
  type DisputeMessage,
} from './DisputeService';

export default function DisputeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [dispute, setDispute] = useState<Dispute | null>(null);
  const [messages, setMessages] = useState<DisputeMessage[]>([]);
  const [resolution, setResolution] = useState('');
  const [reply, setReply] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setError(null);
    Promise.all([getDisputeById(id), getDisputeMessages(id)])
      .then(([d, m]) => {
        setDispute(d);
        setMessages(m);
      })
      .catch(() => setError('Failed to load dispute.'));
  }, [id]);

  const run = async (action: () => Promise<Dispute>, failure: string) => {
    setIsSaving(true);
    setError(null);
    try {
      setDispute(await action());
    } catch {
      setError(failure);
    } finally {
      setIsSaving(false);
    }
  };

  const sendReply = async (event: FormEvent) => {
    event.preventDefault();
    const adminId = currentAdminId();
    if (!dispute || !reply.trim() || !adminId) return;
    setIsSaving(true);
    setError(null);
    try {
      const message = await addDisputeMessage(dispute.id, adminId, reply.trim());
      setMessages((m) => [...m, message]);
      setReply('');
    } catch {
      setError('Failed to send message.');
    } finally {
      setIsSaving(false);
    }
  };

  if (!dispute) return <p className={error ? 'text-red-600' : 'text-gray-500'}>{error ?? 'Loading dispute…'}</p>;

  const isOpen = dispute.status !== 'RESOLVED';

  return (
    <div className="space-y-6 max-w-4xl">
      <button onClick={() => navigate('/disputes')} className="flex items-center gap-1 text-sm text-indigo-600 hover:underline">
        <ArrowLeft size={16} /> Back to Disputes
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="bg-white rounded-2xl shadow p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Case #{dispute.caseNumber}</h1>
            <p className="text-sm text-gray-500 mt-0.5">Opened {format(new Date(dispute.createdAt), 'PPP')}</p>
          </div>
          <span className={`text-sm font-semibold px-3 py-1 rounded-full capitalize ${STATUS_COLORS[dispute.status]}`}>
            {formatStatus(dispute.status)}
          </span>
        </div>
        <div className="grid sm:grid-cols-2 gap-4 text-sm">
          <div><p className="text-gray-500">Type</p><p className="font-medium capitalize">{dispute.type.replace(/_/g, ' ')}</p></div>
          <div><p className="text-gray-500">Raised by</p><p className="font-medium font-mono text-xs">{dispute.raisedBy}</p></div>
          <div><p className="text-gray-500">Booking ID</p><p className="font-medium font-mono text-xs">{dispute.bookingId}</p></div>
          {dispute.resolvedAt && (
            <div><p className="text-gray-500">Resolved</p><p className="font-medium">{format(new Date(dispute.resolvedAt), 'PPp')}</p></div>
          )}
        </div>
        <div className="mt-4">
          <p className="text-gray-500 text-sm">Description</p>
          <p className="mt-1 text-gray-800">{dispute.description}</p>
        </div>
        {dispute.resolution && (
          <div className="mt-4">
            <p className="text-gray-500 text-sm">Resolution</p>
            <p className="mt-1 text-gray-800">{dispute.resolution}</p>
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Evidence ({dispute.evidenceUrls.length})</h2>
        {dispute.evidenceUrls.length === 0 ? (
          <p className="text-gray-400 text-sm">No evidence submitted.</p>
        ) : (
          <ul className="space-y-2">
            {dispute.evidenceUrls.map((url) => (
              <li key={url} className="flex items-center gap-2 text-sm">
                <FileText size={16} className="text-gray-500" />
                <a href={url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline break-all">{url}</a>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="bg-white rounded-2xl shadow p-6 space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">Messages ({messages.length})</h2>
        {messages.length === 0 && <p className="text-gray-400 text-sm">No messages yet.</p>}
        {messages.map((m) => (
          <div key={m.id} className="bg-gray-50 rounded-xl p-3 text-sm">
            <p className="text-gray-800">{m.content}</p>
            <p className="text-xs text-gray-400 mt-1">{m.authorId} · {format(new Date(m.createdAt), 'PPp')}</p>
          </div>
        ))}
        <form onSubmit={sendReply} className="flex gap-2">
          <input value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Write a message…" className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          <button type="submit" disabled={isSaving || !reply.trim()} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">Send</button>
        </form>
      </div>

      {isOpen && (
        <div className="bg-white rounded-2xl shadow p-6 space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">Actions</h2>
          {dispute.status === 'OPEN' && (
            <button onClick={() => run(() => startReview(dispute.id), 'Failed to start review.')} disabled={isSaving} className="bg-yellow-500 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-yellow-600 disabled:opacity-50">
              Start review
            </button>
          )}
          {dispute.status === 'UNDER_REVIEW' && (
            <button onClick={() => run(() => escalateDispute(dispute.id), 'Failed to escalate.')} disabled={isSaving} className="bg-orange-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-orange-700 disabled:opacity-50">
              Escalate
            </button>
          )}
          <textarea value={resolution} onChange={(e) => setResolution(e.target.value)} rows={3} placeholder="Resolution notes (required to resolve)…" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <button onClick={() => run(() => resolveDispute(dispute.id, resolution.trim()), 'Failed to resolve dispute.')} disabled={isSaving || !resolution.trim()} className="bg-green-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
            Mark resolved
          </button>
        </div>
      )}
    </div>
  );
}
