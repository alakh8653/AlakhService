import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { CheckCircle2, Circle, FileText, Trash2, Upload } from 'lucide-react';
import type { AppDispatch, RootState } from '../state/store';
import { setShop } from '../state/authSlice';
import { updateShop, verificationOf } from '../services/shopService';
import {
  DOCUMENT_LABELS,
  DOCUMENT_TYPES,
  deleteDocument,
  downloadDocument,
  fileProblem,
  getDocuments,
  getPayoutDetails,
  isValidGstin,
  submitForReview,
  uploadDocument,
  type DocumentType,
  type ShopDocument,
} from '../services/kycService';
import { apiErrorMessage } from '../services/format';
import { useToast } from '../components/Toast';
import PayoutDetailsForm from '../components/PayoutDetailsForm';
import type { Shop } from '../types';

const inputClass =
  'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400 disabled:bg-gray-50 disabled:text-gray-500';
const card = 'bg-white rounded-xl border border-gray-200 p-4 md:p-6 space-y-4';

const docLabel = (type: string) => DOCUMENT_LABELS[type as DocumentType] ?? type;

export interface ChecklistItem {
  id: string;
  label: string;
  done: boolean;
  required: boolean;
}

/** What the owner still has to do; the required items match shop_service's submit check. */
export function onboardingChecklist(shop: Shop, documents: ShopDocument[], hasPayout: boolean): ChecklistItem[] {
  const has = (type: string) => documents.some((d) => d.type === type);
  const items: ChecklistItem[] = [
    { id: 'legal', label: 'Legal business name', done: !!shop.legalName, required: true },
    { id: 'pan', label: 'PAN card uploaded', done: has('PAN'), required: true },
  ];
  if (shop.gstin) items.push({ id: 'gst', label: 'GST certificate uploaded (you gave a GSTIN)', done: has('GST'), required: true });
  items.push(
    { id: 'photo', label: 'Shop photo (helps customers find you)', done: has('SHOP_PHOTO'), required: false },
    { id: 'payout', label: 'Payout details, so we can pay you', done: hasPayout, required: false },
  );
  return items;
}

function LegalDetailsForm({ shop, locked }: { shop: Shop; locked: boolean }) {
  const dispatch = useDispatch<AppDispatch>();
  const toast = useToast();
  const [legalName, setLegalName] = useState(shop.legalName ?? '');
  const [legalAddress, setLegalAddress] = useState(shop.legalAddress ?? '');
  const [gstin, setGstin] = useState(shop.gstin ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gstinInvalid = gstin.trim() !== '' && !isValidGstin(gstin);
  const nameInvalid = legalName.trim().length > 0 && legalName.trim().length < 2;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (gstinInvalid || nameInvalid || saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateShop(shop.id, {
        legal_name: legalName.trim() || null,
        legal_address: legalAddress.trim() || null,
        gstin: gstin.trim().toUpperCase() || null,
      });
      dispatch(setShop(updated));
      toast('Business details saved');
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save your business details'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={(e) => void save(e)} noValidate className="space-y-4" aria-label="Business details">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="legal-name" className="block text-sm font-medium text-gray-700 mb-1">
            Legal business name
          </label>
          <input
            id="legal-name"
            value={legalName}
            onChange={(e) => setLegalName(e.target.value)}
            disabled={locked}
            maxLength={200}
            autoComplete="organization"
            aria-invalid={nameInvalid}
            className={inputClass}
            placeholder="As on your PAN or GST certificate"
          />
        </div>
        <div>
          <label htmlFor="gstin" className="block text-sm font-medium text-gray-700 mb-1">
            GSTIN (optional)
          </label>
          <input
            id="gstin"
            value={gstin}
            onChange={(e) => setGstin(e.target.value.toUpperCase())}
            disabled={locked}
            maxLength={15}
            spellCheck={false}
            autoComplete="off"
            aria-invalid={gstinInvalid}
            aria-describedby={gstinInvalid ? 'gstin-error' : 'gstin-hint'}
            className={`${inputClass} font-mono`}
            placeholder="27AAPFU0939F1ZV"
          />
          {gstinInvalid ? (
            <p id="gstin-error" className="mt-1 text-xs text-red-600">
              This is not a valid GSTIN. Check the 15 characters.
            </p>
          ) : (
            <p id="gstin-hint" className="mt-1 text-xs text-gray-500">
              Only if your business is GST-registered. It appears on customers' invoices.
            </p>
          )}
        </div>
      </div>
      <div>
        <label htmlFor="legal-address" className="block text-sm font-medium text-gray-700 mb-1">
          Registered address (optional)
        </label>
        <textarea id="legal-address" value={legalAddress} onChange={(e) => setLegalAddress(e.target.value)} rows={2} maxLength={500} className={inputClass} />
      </div>
      {locked && <p className="text-xs text-gray-500">Your verified legal name and GSTIN can only be changed by our support team.</p>}
      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      <button type="submit" disabled={saving} className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50">
        {saving ? 'Saving…' : 'Save business details'}
      </button>
    </form>
  );
}

function DocumentUpload({ shopId, onAdded }: { shopId: string; onAdded: (doc: ShopDocument) => void }) {
  const toast = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const hintId = useId();
  const [type, setType] = useState<DocumentType>('PAN');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Choose a file first.');
      return;
    }
    const problem = fileProblem(file);
    if (problem) {
      setError(problem);
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(shopId, type, file);
      onAdded(doc);
      setFile(null);
      if (fileInput.current) fileInput.current.value = '';
      toast(`${docLabel(type)} uploaded`);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not upload the file'));
    } finally {
      setUploading(false);
    }
  };

  return (
    <form onSubmit={(e) => void upload(e)} className="grid grid-cols-1 sm:grid-cols-[1fr_1.5fr_auto] gap-3 items-end" aria-label="Upload a document">
      <div>
        <label htmlFor="doc-type" className="block text-sm font-medium text-gray-700 mb-1">
          Document
        </label>
        <select id="doc-type" value={type} onChange={(e) => setType(e.target.value as DocumentType)} className={inputClass}>
          {DOCUMENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {DOCUMENT_LABELS[t]}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="doc-file" className="block text-sm font-medium text-gray-700 mb-1">
          File
        </label>
        <input
          id="doc-file"
          ref={fileInput}
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/webp"
          aria-describedby={hintId}
          aria-invalid={!!error}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setError(null);
          }}
          className="block w-full text-sm text-gray-700 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-2 file:text-indigo-700"
        />
      </div>
      <button
        type="submit"
        disabled={uploading}
        className="inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
      >
        <Upload size={16} aria-hidden /> {uploading ? 'Uploading…' : 'Upload'}
      </button>
      <p id={hintId} className="sm:col-span-3 text-xs text-gray-500">
        PDF, JPG, PNG or WebP, up to 5 MB. Only you and our verification team can see these files.
      </p>
      {error && (
        <p role="alert" className="sm:col-span-3 text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
    </form>
  );
}

/** KYC: business details, documents, payout details and submitting the shop for review. */
export default function OnboardingPage() {
  const dispatch = useDispatch<AppDispatch>();
  const toast = useToast();
  const shop = useSelector((state: RootState) => state.auth.shop);
  const [documents, setDocuments] = useState<ShopDocument[]>([]);
  const [hasPayout, setHasPayout] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const shopId = shop?.id;

  useEffect(() => {
    if (!shopId) return;
    let live = true;
    getDocuments(shopId)
      .then((docs) => live && setDocuments(docs))
      .catch((e) => live && setLoadError(apiErrorMessage(e, 'Could not load your documents.')));
    getPayoutDetails(shopId)
      .then((d) => live && setHasPayout(!!d))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [shopId]);

  if (!shop) return null;
  const status = verificationOf(shop);
  const checklist = onboardingChecklist(shop, documents, hasPayout);
  const ready = checklist.every((i) => !i.required || i.done);
  const waiting = status === 'PENDING_REVIEW' && !!shop.submittedAt;

  const view = async (doc: ShopDocument) => {
    if (!doc.uploaded) {
      window.open(doc.url, '_blank', 'noopener,noreferrer');
      return;
    }
    try {
      const url = URL.createObjectURL(await downloadDocument(shop.id, doc.id));
      window.open(url, '_blank', 'noopener');
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      toast(apiErrorMessage(e, 'Could not open the file'), 'error');
    }
  };

  const remove = async (doc: ShopDocument) => {
    try {
      await deleteDocument(shop.id, doc.id);
      setDocuments((list) => list.filter((d) => d.id !== doc.id));
      toast('Document removed');
    } catch (e) {
      toast(apiErrorMessage(e, 'Could not remove the document'), 'error');
    }
  };

  const submit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      dispatch(setShop(await submitForReview(shop.id)));
      toast('Submitted for review. We usually reply within 2 working days.');
    } catch (e) {
      setSubmitError(apiErrorMessage(e, 'Could not submit for review'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Verification</h1>
        <p className="text-sm text-gray-500">
          {status === 'APPROVED'
            ? 'Your shop is verified and visible to customers.'
            : 'Customers can find and book your shop once our team has verified these details.'}
        </p>
      </div>

      {status === 'REJECTED' && (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <p className="font-semibold">We could not verify your shop</p>
          {shop.rejectionReason && <p className="mt-1">{shop.rejectionReason}</p>}
          <p className="mt-1">Fix the details below and submit again.</p>
        </div>
      )}

      {status !== 'APPROVED' && (
        <section aria-labelledby="checklist-heading" className={card}>
          <h2 id="checklist-heading" className="text-lg font-semibold text-gray-900">
            Checklist
          </h2>
          <ul className="space-y-2">
            {checklist.map((item) => (
              <li key={item.id} className="flex items-center gap-2 text-sm">
                {item.done ? (
                  <CheckCircle2 size={18} className="text-green-600 shrink-0" aria-hidden />
                ) : (
                  <Circle size={18} className="text-gray-300 shrink-0" aria-hidden />
                )}
                <span className={item.done ? 'text-gray-900' : 'text-gray-600'}>
                  {item.label}
                  {!item.required && <span className="text-gray-400"> (recommended)</span>}
                  <span className="sr-only">{item.done ? ': done' : ': to do'}</span>
                </span>
              </li>
            ))}
          </ul>
          {waiting ? (
            <p className="text-sm text-indigo-800 bg-indigo-50 rounded-lg px-3 py-2">
              Submitted for review. We will tell you as soon as our team has checked your documents.
            </p>
          ) : (
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => void submit()}
                disabled={!ready || submitting}
                className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
              >
                {submitting ? 'Submitting…' : status === 'REJECTED' ? 'Submit again' : 'Submit for review'}
              </button>
              {!ready && <p className="text-xs text-gray-500">Complete the required items above to submit.</p>}
              {submitError && (
                <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
                  {submitError}
                </p>
              )}
            </div>
          )}
        </section>
      )}

      <section aria-labelledby="business-heading" className={card}>
        <h2 id="business-heading" className="text-lg font-semibold text-gray-900">
          Business details
        </h2>
        <LegalDetailsForm key={shop.id} shop={shop} locked={status === 'APPROVED'} />
      </section>

      <section aria-labelledby="documents-heading" className={card}>
        <h2 id="documents-heading" className="text-lg font-semibold text-gray-900">
          Documents
        </h2>
        {loadError && (
          <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
            {loadError}
          </p>
        )}
        {documents.length > 0 ? (
          <ul className="divide-y divide-gray-100" aria-label="Your documents">
            {documents.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
                <FileText size={16} className="text-gray-400 shrink-0" aria-hidden />
                <span className="font-medium text-gray-900">{docLabel(d.type)}</span>
                {d.fileName && <span className="text-gray-500 break-all">{d.fileName}</span>}
                {d.isVerified && <span className="text-xs font-medium text-green-700">Verified</span>}
                <span className="ml-auto flex items-center gap-3">
                  <button type="button" onClick={() => void view(d)} className="text-indigo-600 font-medium hover:underline">
                    View<span className="sr-only"> {docLabel(d.type)}</span>
                  </button>
                  {!d.isVerified && (
                    <button type="button" onClick={() => void remove(d)} aria-label={`Remove ${docLabel(d.type)}`} className="p-1 rounded text-gray-500 hover:text-red-600">
                      <Trash2 size={16} aria-hidden />
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          !loadError && <p className="text-sm text-gray-500">No documents yet. Start with your PAN card.</p>
        )}
        <DocumentUpload shopId={shop.id} onAdded={(doc) => setDocuments((list) => [...list, doc])} />
      </section>

      <section aria-labelledby="payout-heading" className={card}>
        <h2 id="payout-heading" className="text-lg font-semibold text-gray-900">
          Payout details
        </h2>
        <PayoutDetailsForm shopId={shop.id} onSaved={() => setHasPayout(true)} />
      </section>
    </div>
  );
}
