import axios from 'axios';
import adminApiClient from '../apiClient';

// Providers' work photos go live with no check before, so admins look here at what customers reported.

export type PhotoStatus = 'reported' | 'hidden' | 'all';

export interface WorkPhoto {
  id: string;
  shopId: string;
  shopName: string;
  url: string;
  caption: string | null;
  isHidden: boolean;
  reportCount: number;
  reportReasons: string[];
  createdAt: string;
}

interface WorkPhotoRecord {
  id: string;
  shop_id: string;
  shop_name: string;
  url: string;
  caption?: string | null;
  is_hidden: boolean;
  report_count: number;
  report_reasons: string[];
  created_at: string;
}

const toPhoto = (r: WorkPhotoRecord): WorkPhoto => ({
  id: r.id,
  shopId: r.shop_id,
  shopName: r.shop_name,
  url: r.url,
  caption: r.caption ?? null,
  isHidden: r.is_hidden,
  reportCount: r.report_count,
  reportReasons: r.report_reasons,
  createdAt: r.created_at,
});

export const PER_PAGE = 24;

export async function getWorkPhotos(status: PhotoStatus, page: number): Promise<{ photos: WorkPhoto[]; total: number }> {
  const { data } = await adminApiClient.get<{ items: WorkPhotoRecord[]; total: number }>('/admin/work-photos', {
    params: { status, skip: (page - 1) * PER_PAGE, limit: PER_PAGE },
  });
  return { photos: data.items.map(toPhoto), total: data.total };
}

export async function setPhotoHidden(id: string, hidden: boolean): Promise<WorkPhoto> {
  const { data } = await adminApiClient.put<WorkPhotoRecord>(`/admin/work-photos/${encodeURIComponent(id)}`, { hidden });
  return toPhoto(data);
}

export async function removePhoto(id: string): Promise<void> {
  await adminApiClient.delete(`/admin/work-photos/${encodeURIComponent(id)}`);
}

/** The image, as a Blob: a hidden photo needs the admin's token, so it cannot be a plain link. */
export async function fetchPhotoFile(photo: WorkPhoto): Promise<Blob> {
  const token = localStorage.getItem('admin_token');
  const { data } = await axios.get<Blob>(photo.url.replace(/^\/api\/v1/, ''), {
    baseURL: adminApiClient.defaults.baseURL,
    responseType: 'blob',
    timeout: 30_000,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  return data;
}
