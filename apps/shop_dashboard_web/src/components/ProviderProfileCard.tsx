import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react';
import { apiErrorMessage } from '../services/format';
import {
  MAX_PHOTO_BYTES,
  PHOTO_TYPES,
  PROFILE_LANGUAGES,
  addPhoto,
  getProfile,
  removePhoto,
  saveProfile,
  type WorkPhoto,
} from '../services/profileService';
import { useToast } from './Toast';

/** Experience, languages and photos of the work, which customers see before they book. */
export default function ProviderProfileCard({ shopId }: { shopId: string }) {
  const toast = useToast();
  const file = useRef<HTMLInputElement>(null);
  const [years, setYears] = useState('');
  const [languages, setLanguages] = useState<string[]>([]);
  const [photos, setPhotos] = useState<WorkPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const profile = await getProfile(shopId);
      setYears(profile.yearsExperience?.toString() ?? '');
      setLanguages(profile.languages);
      setPhotos(profile.photos);
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not load your profile.'));
    } finally {
      setLoading(false);
    }
  }, [shopId]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (action: () => Promise<void>, done?: string) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      if (done) toast(done);
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not save that.'));
    } finally {
      setBusy(false);
    }
  };

  const save = () => {
    const value = years.trim() === '' ? null : Number(years);
    if (value !== null && (!Number.isInteger(value) || value < 0 || value > 70)) {
      setError('Enter your years of experience as a number from 0 to 70.');
      return;
    }
    void run(() => saveProfile(shopId, value, languages), 'Saved. Customers can see this.');
  };

  const upload = (e: ChangeEvent<HTMLInputElement>) => {
    const chosen = e.target.files?.[0];
    e.target.value = '';
    if (!chosen) return;
    if (!PHOTO_TYPES.includes(chosen.type)) {
      setError('Choose a JPEG, PNG or WebP photo.');
      return;
    }
    if (chosen.size > MAX_PHOTO_BYTES) {
      setError('That photo is too large (max 5 MB).');
      return;
    }
    void run(async () => {
      await addPhoto(shopId, chosen);
      await load();
    });
  };

  if (loading) return null;

  return (
    <section aria-label="Your profile and work photos" className="bg-white rounded-xl border border-gray-200 p-4 md:p-6 mt-6 space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Your profile and work photos</h2>
        <p className="text-sm text-gray-600">Customers see this before they book. It helps them choose you.</p>
      </div>
      <label className="block text-sm font-medium text-gray-700 max-w-xs">
        Years of experience
        <input
          type="number"
          min="0"
          max="70"
          value={years}
          onChange={(e) => setYears(e.target.value)}
          className="mt-1 block w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </label>
      <fieldset>
        <legend className="text-sm font-medium text-gray-700 mb-2">Languages you speak</legend>
        <div className="flex flex-wrap gap-3">
          {PROFILE_LANGUAGES.map((language) => (
            <label key={language} className="flex items-center gap-2 text-sm text-gray-800">
              <input
                type="checkbox"
                checked={languages.includes(language)}
                onChange={(e) => setLanguages(e.target.checked ? [...languages, language] : languages.filter((l) => l !== language))}
              />
              {language}
            </label>
          ))}
        </div>
      </fieldset>
      <button type="button" disabled={busy} onClick={save} className="bg-indigo-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-50">
        Save profile
      </button>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      <div>
        <h3 className="text-sm font-semibold text-gray-900">Photos of your work</h3>
        <p className="text-xs text-gray-500 mb-2">
          Show finished jobs. Don't show customers' faces or documents. We remove location details from photos.
        </p>
        <ul className="flex flex-wrap gap-3">
          {photos.map((photo) => (
            <li key={photo.id} className="w-32 space-y-1">
              <img src={photo.url} alt={photo.caption ?? 'Your work'} className="h-32 w-32 object-cover rounded-lg bg-gray-100" />
              {photo.isHidden && <p className="text-xs font-semibold text-red-700">Hidden while we check</p>}
              <button
                type="button"
                disabled={busy}
                aria-label={`Remove photo ${photo.caption ?? ''}`.trim()}
                onClick={() =>
                  void run(async () => {
                    await removePhoto(shopId, photo.id);
                    await load();
                  })
                }
                className="text-xs text-red-700"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <input ref={file} type="file" accept={PHOTO_TYPES.join(',')} aria-label="Add a photo" onChange={upload} className="mt-3 block text-sm text-gray-700" disabled={busy} />
      </div>
    </section>
  );
}
