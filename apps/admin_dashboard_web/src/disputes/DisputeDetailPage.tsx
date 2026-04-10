import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { getDisputeById, updateDisputeStatus, type Dispute, type DisputeStatus } from './DisputeService';
import { ArrowLeft, FileText, Image } from 'lucide-react';

export default function DisputeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [dispute, setDispute] = useState<Dispute | null>(null);
  const [resolution, setResolution] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (id) getDisputeById(id).then(setDispute);
  }, [id]);

  const handleResolve = async (status: DisputeStatus) => {
    if (!dispute) return;
    setIsSaving(true);
    try {
      const updated = await updateDisputeStatus(dispute.id, status, resolution);
      setDispute(updated);
    } finally {
      setIsSaving(false);
    }
  };

  if (!dispute) return <p className="text-gray-500">Loading dispute…</p>;

  return (
    <div className="space-y-6 max-w-4xl">
      <button onClick={() => navigate('/disputes')} className="flex items-center gap-1 text-sm text-indigo-600 hover:underline">
        <ArrowLeft size={16} /> Back to Disputes
      </button>
      <div className="bg-white rounded-2xl shadow p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Case #{dispute.caseNumber}</h1>
            <p className="text-sm text-gray-500 mt-0.5">Opened {format(new Date(dispute.createdAt), 'PPP')}</p>
          </div>
          <span className="text-sm font-semibold px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full capitalize">
            {dispute.status.replace('_', ' ')}
          </span>
        </div>
        <div className="grid sm:grid-cols-2 gap-4 text-sm">
          <div><p className="text-gray-500">Customer</p><p className="font-medium">{dispute.customerName}</p></div>
          <div><p className="text-gray-500">Shop</p><p className="font-medium">{dispute.shopName}</p></div>
          <div><p className="text-gray-500">Reason</p><p className="font-medium">{dispute.reason}</p></div>
          <div><p className="text-gray-500">Booking ID</p><p className="font-medium font-mono text-xs">{dispute.bookingId}</p></div>
        </div>
        <div className="mt-4">
          <p className="text-gray-500 text-sm">Description</p>
          <p className="mt-1 text-gray-800">{dispute.description}</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Evidence ({dispute.evidence.length})</h2>
        {dispute.evidence.length === 0 ? <p className="text-gray-400 text-sm">No evidence submitted.</p> : (
          <div className="space-y-3">
            {dispute.evidence.map((e) => (
              <div key={e.id} className="flex items-start gap-3 bg-gray-50 rounded-xl p-3">
                {e.type === 'image' ? <Image size={18} className="text-blue-500 mt-0.5" /> : <FileText size={18} className="text-gray-500 mt-0.5" />}
                <div className="flex-1 text-sm">
                  <p className="font-medium text-gray-900 capitalize">{e.type}</p>
                  {e.content && <p className="text-gray-600 mt-0.5">{e.content}</p>}
                  {e.url && <a href={e.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline text-xs">{e.url}</a>}
                  <p className="text-xs text-gray-400 mt-1">By {e.submittedBy} · {format(new Date(e.createdAt), 'PPp')}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {dispute.status !== 'resolved' && dispute.status !== 'closed' && (
        <div className="bg-white rounded-2xl shadow p-6 space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">Resolve Dispute</h2>
          <textarea value={resolution} onChange={(e) => setResolution(e.target.value)} rows={3} placeholder="Enter resolution notes…" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <div className="flex gap-3">
            <button onClick={() => handleResolve('resolved')} disabled={isSaving} className="bg-green-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
              Mark Resolved
            </button>
            <button onClick={() => handleResolve('closed')} disabled={isSaving} className="bg-gray-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-gray-700 disabled:opacity-50">
              Close Without Resolution
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
