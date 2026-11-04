import { useCallback, useEffect, useState } from 'react';
import ConfirmDialog from '../components/ConfirmDialog';
import { useToast } from '../components/Toast';
import { apiErrorMessage } from '../shared/apiError';
import { formatDateTime } from '../shared/format';
import {
  PER_PAGE,
  fetchPhotoFile,
  getWorkPhotos,
  removePhoto,
  setPhotoHidden,
  type PhotoStatus,
  type WorkPhoto,
} from './WorkPhotoService';

const TABS: { value: PhotoStatus; label: string }[] = [
  { value: 'reported', label: 'Reported' },
  { value: 'hidden', label: 'Hidden' },
  { value: 'all', label: 'All photos' },
];

/** The image, fetched with the admin's token so that hidden photos can be judged too. */
function PhotoImage({ photo }: { photo: WorkPhoto }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    let url: string | null = null;
    fetchPhotoFile(photo)
      .then((blob) => {
        if (!live) return;
        url = URL.createObjectURL(blob);
        setSrc(url);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [photo]);

  if (failed) return <div className="h-48 bg-gray-100 rounded-lg flex items-center justify-center text-sm text-gray-500">Could not load the photo</div>;
  if (!src) return <div className="h-48 bg-gray-100 rounded-lg" aria-hidden="true" />;
  return <img src={src} alt={photo.caption ?? `Work photo from ${photo.shopName}`} className="h-48 w-full object-cover rounded-lg" />;
}

/** Providers' work photos: what customers reported, what is hidden, and everything to look through. */
export default function WorkPhotosPage() {
  const toast = useToast();
  const [status, setStatus] = useState<PhotoStatus>('reported');
  const [page, setPage] = useState(1);
  const [photos, setPhotos] = useState<WorkPhoto[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<WorkPhoto | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getWorkPhotos(status, page);
      setPhotos(result.photos);
      setTotal(result.total);
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not load the photos.'));
    } finally {
      setLoading(false);
    }
  }, [status, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = async (photo: WorkPhoto, hidden: boolean) => {
    try {
      await setPhotoHidden(photo.id, hidden);
      toast(hidden ? 'Photo hidden; the owner has been told.' : 'Photo kept, and its reports cleared.');
      await load();
    } catch (e) {
      toast(apiErrorMessage(e, 'Could not save that.'), 'error');
    }
  };

  const pages = Math.max(1, Math.ceil(total / PER_PAGE));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Work photos</h1>
        <p className="text-sm text-gray-600">
          Photos go live with no check before. Three different people reporting one hides it until you look.
        </p>
      </div>
      <div role="group" aria-label="Which photos" className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            aria-pressed={status === tab.value}
            onClick={() => {
              setStatus(tab.value);
              setPage(1);
            }}
            className={`rounded-full px-4 py-1.5 text-sm font-medium ${status === tab.value ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {!loading && !error && photos.length === 0 && <p className="text-sm text-gray-600">Nothing here.</p>}
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {photos.map((photo) => (
          <li key={photo.id} className="bg-white rounded-xl shadow p-3 space-y-2">
            <PhotoImage photo={photo} />
            <p className="text-sm font-semibold text-gray-900">{photo.shopName}</p>
            {photo.caption && <p className="text-sm text-gray-700">{photo.caption}</p>}
            <p className="text-xs text-gray-500">Added {formatDateTime(photo.createdAt)}</p>
            {photo.isHidden && <p className="text-xs font-semibold text-red-700">Hidden from customers</p>}
            {photo.reportCount > 0 && (
              <div className="text-sm text-amber-900 bg-amber-50 rounded-lg px-2 py-1">
                <p className="font-semibold">
                  Reported by {photo.reportCount} {photo.reportCount === 1 ? 'person' : 'people'}
                </p>
                <ul className="list-disc ml-4">
                  {photo.reportReasons.map((reason, i) => (
                    <li key={i}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {(photo.isHidden || photo.reportCount > 0) && (
                <button type="button" onClick={() => void decide(photo, false)} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium">
                  {photo.isHidden ? 'Show again' : 'Keep'}
                </button>
              )}
              {!photo.isHidden && (
                <button type="button" onClick={() => void decide(photo, true)} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium">
                  Hide
                </button>
              )}
              <button type="button" onClick={() => setRemoving(photo)} className="rounded-lg bg-red-600 text-white px-3 py-1.5 text-sm font-medium">
                Remove
              </button>
            </div>
          </li>
        ))}
      </ul>
      {pages > 1 && (
        <nav aria-label="Pages" className="flex items-center gap-3 text-sm">
          <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded border px-3 py-1 disabled:opacity-50">
            Previous
          </button>
          <span>
            Page {page} of {pages}
          </span>
          <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)} className="rounded border px-3 py-1 disabled:opacity-50">
            Next
          </button>
        </nav>
      )}
      {removing && (
        <ConfirmDialog
          title={`Remove this photo from ${removing.shopName}?`}
          confirmLabel="Remove photo"
          tone="danger"
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            await removePhoto(removing.id);
            setRemoving(null);
            toast('Photo removed; the owner has been told.');
            await load();
          }}
        >
          <p>It is deleted for good and cannot be brought back. The owner is told, without the reason.</p>
        </ConfirmDialog>
      )}
    </div>
  );
}
