import apiClient from './apiClient';

// What customers see of a business before booking: experience, languages and photos of its work.

export interface WorkPhoto {
  id: string;
  /** Full address of the image. */
  url: string;
  caption: string | null;
  isHidden: boolean;
}

export interface ProviderProfile {
  yearsExperience: number | null;
  languages: string[];
  photos: WorkPhoto[];
}

export const PROFILE_LANGUAGES = ['Hindi', 'English', 'Bengali', 'Marathi', 'Telugu', 'Tamil', 'Gujarati', 'Urdu', 'Kannada', 'Odia', 'Malayalam', 'Punjabi'];
export const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
export const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

interface PhotoRecord {
  id: string;
  url: string;
  caption?: string | null;
  is_hidden?: boolean;
}

// The API's address ends in /api/v1, and so does the start of each image's path.
const origin = () => (apiClient.defaults.baseURL ?? '').replace(/\/api\/v1\/?$/, '');

const toPhoto = (r: PhotoRecord): WorkPhoto => ({
  id: r.id,
  url: `${origin()}${r.url}`,
  caption: r.caption ?? null,
  isHidden: !!r.is_hidden,
});

const base = (shopId: string) => `/shops/${encodeURIComponent(shopId)}`;

export async function getProfile(shopId: string): Promise<ProviderProfile> {
  const [shop, photos] = await Promise.all([
    apiClient.get<{ years_experience?: number | null; languages?: string[] | null }>(base(shopId)),
    apiClient.get<PhotoRecord[]>(`${base(shopId)}/photos`),
  ]);
  return {
    yearsExperience: shop.data.years_experience ?? null,
    languages: shop.data.languages ?? [],
    photos: photos.data.map(toPhoto),
  };
}

export async function saveProfile(shopId: string, yearsExperience: number | null, languages: string[]): Promise<void> {
  await apiClient.put(base(shopId), { years_experience: yearsExperience, languages });
}

/** The raw file is the request body, as shop_service expects. */
export async function addPhoto(shopId: string, file: File): Promise<void> {
  await apiClient.post(`${base(shopId)}/photos`, file, { headers: { 'Content-Type': file.type } });
}

export async function removePhoto(shopId: string, photoId: string): Promise<void> {
  await apiClient.delete(`${base(shopId)}/photos/${encodeURIComponent(photoId)}`);
}
