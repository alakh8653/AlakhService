import { useState } from 'react';
import { CheckCircle2, ExternalLink, FileText, XCircle } from 'lucide-react';
import ConfirmDialog from '../components/ConfirmDialog';
import { useToast } from '../components/Toast';
import { apiErrorMessage } from '../shared/apiError';
import { formatDateTime, shortId } from '../shared/format';
import {
  STATUS_LABELS,
  approveShop,
  documentLabel,
  fetchDocumentFile,
  rejectShop,
  type AdminShop,
  type ShopDocument,
  type ShopForReview,
  type VerificationStatus,
} from './ShopReviewService';

const STATUS_CLASS: Record<VerificationStatus, string> = {
  PENDING_REVIEW: 'bg-yellow-100 text-yellow-800',
  APPROVED: 'bg-green-100 text-green-800',
  REJECTED: 'bg-red-100 text-red-800',
};

export function StatusBadge({ status }: { status: VerificationStatus }) {
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_CLASS[status]}`}>{STATUS_LABELS[status]}</span>;
}

function fileSize(bytes: number | null): string {
  if (!bytes) return '';
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function DocumentRow({ shopId, doc }: { shopId: string; doc: ShopDocument }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const label = `${documentLabel(doc.type)}${doc.fileName ? ` (${doc.fileName})` : ''}`;

  const open = async () => {
    setBusy(true);
    setError(null);
    // Opened synchronously so pop-up blockers allow it; filled in once the file has arrived.
    const tab = window.open('', '_blank');
    try {
      const blob = await fetchDocumentFile(shopId, doc);
      const url = URL.createObjectURL(blob);
      if (tab) tab.location.href = url;
      else window.location.assign(url);
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      tab?.close();
      setError(apiErrorMessage(e, 'Could not open the file.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
      <FileText size={16} aria-hidden="true" className="text-gray-500 shrink-0" />
      <span className="text-sm text-gray-900 break-all">{label}</span>
      {doc.sizeBytes ? <span className="text-xs text-gray-500">{fileSize(doc.sizeBytes)}</span> : null}
      {doc.isVerified && <span className="text-xs font-medium text-green-700">Verified</span>}
      <span className="ml-auto">
        {doc.uploaded ? (
          <button
            type="button"
            onClick={() => void open()}
            disabled={busy}
            aria-label={`View ${label}`}
            className="text-sm font-medium text-indigo-700 hover:underline disabled:opacity-50"
          >
            {busy ? 'Opening…' : 'View'}
          </button>
        ) : (
          <a
            href={doc.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            aria-label={`Open ${label} (external link)`}
            className="inline-flex items-center gap-1 text-sm font-medium text-indigo-700 hover:underline"
          >
            Open link <ExternalLink size={14} aria-hidden="true" />
          </a>
        )}
      </span>
      {error && (
        <span role="alert" className="basis-full text-xs text-red-700">
          {error}
        </span>
      )}
    </li>
  );
}

function Detail({ term, value }: { term: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500">{term}</dt>
      <dd className="text-sm text-gray-900 break-words">{value || <span className="text-gray-400">Not given</span>}</dd>
    </div>
  );
}

/** One shop's KYC details and documents, with the approve and reject actions. */
export default function ShopReviewCard({ shop, onDecided }: { shop: ShopForReview; onDecided: (shop: AdminShop) => void }) {
  const notify = useToast();
  const [action, setAction] = useState<'approve' | 'reject' | null>(null);
  const headingId = `shop-${shop.id}`;

  return (
    <article aria-labelledby={headingId} className="bg-white rounded-xl shadow p-4 sm:p-6 space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 id={headingId} className="text-lg font-semibold text-gray-900">
            {shop.name}
          </h3>
          <p className="text-sm text-gray-600">
            {shop.category}
            {shop.city ? ` · ${shop.city}` : ''} · <span title={shop.id} className="font-mono text-xs">{shortId(shop.id)}</span>
          </p>
        </div>
        <StatusBadge status={shop.status} />
      </header>

      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Detail term="Legal name" value={shop.legalName} />
        <Detail term="GSTIN" value={shop.gstin} />
        <Detail term="Legal address" value={shop.legalAddress ?? shop.address} />
        <Detail term="Contact" value={[shop.phone, shop.email].filter(Boolean).join(' · ')} />
        <Detail term="Submitted" value={shop.submittedAt ? formatDateTime(shop.submittedAt) : null} />
        <Detail term="Payout details" value={shop.hasPayoutDetails ? 'Added' : null} />
      </dl>
      {shop.status === 'REJECTED' && shop.rejectionReason && (
        <p className="text-sm text-red-800 bg-red-50 rounded-lg px-3 py-2">Rejected: {shop.rejectionReason}</p>
      )}

      <section aria-label={`Documents of ${shop.name}`}>
        <h4 className="text-sm font-semibold text-gray-900">Documents ({shop.documents.length})</h4>
        {shop.documents.length === 0 ? (
          <p className="text-sm text-gray-500 py-2">No documents uploaded.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {shop.documents.map((d) => (
              <DocumentRow key={d.id} shopId={shop.id} doc={d} />
            ))}
          </ul>
        )}
      </section>

      <div className="flex flex-col sm:flex-row gap-2 sm:justify-end">
        <button
          type="button"
          onClick={() => setAction('reject')}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
        >
          <XCircle size={16} aria-hidden="true" /> Reject
        </button>
        {shop.status !== 'APPROVED' && (
          <button
            type="button"
            onClick={() => setAction('approve')}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            <CheckCircle2 size={16} aria-hidden="true" /> Approve
          </button>
        )}
      </div>

      {action === 'approve' && (
        <ConfirmDialog
          title={`Approve ${shop.name}?`}
          confirmLabel="Approve shop"
          onCancel={() => setAction(null)}
          onConfirm={async () => {
            const updated = await approveShop(shop.id);
            setAction(null);
            notify(`${shop.name} is approved and now visible to customers.`);
            onDecided(updated);
          }}
        >
          <p>Customers will be able to find and book this shop. Its documents are marked as verified.</p>
        </ConfirmDialog>
      )}
      {action === 'reject' && (
        <ConfirmDialog
          title={`Reject ${shop.name}?`}
          confirmLabel="Reject shop"
          tone="danger"
          reason={{ label: 'Reason shown to the owner', placeholder: 'e.g. The PAN card photo is blurred', required: true }}
          onCancel={() => setAction(null)}
          onConfirm={async (reason) => {
            if (reason.length < 5) throw { response: { data: { detail: 'Please give a reason of at least 5 characters.' } } };
            const updated = await rejectShop(shop.id, reason);
            setAction(null);
            notify(`${shop.name} was rejected; the owner has been told why.`);
            onDecided(updated);
          }}
        >
          <p>The shop stays hidden from customers. The owner sees your reason and can fix it and submit again.</p>
        </ConfirmDialog>
      )}
    </article>
  );
}
