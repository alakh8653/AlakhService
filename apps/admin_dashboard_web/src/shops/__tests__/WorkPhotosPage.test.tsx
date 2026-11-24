import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import adminApiClient from '../../apiClient';
import WorkPhotosPage from '../WorkPhotosPage';
import * as service from '../WorkPhotoService';

const toast = vi.fn();
vi.mock('../../components/Toast', () => ({ useToast: () => toast }));

const photo: service.WorkPhoto = {
  id: 'p1',
  shopId: 's1',
  shopName: 'Ravi Electricals',
  url: '/api/v1/shops/s1/photos/p1/file',
  caption: 'New wiring',
  isHidden: false,
  reportCount: 2,
  reportReasons: ['Shows a customer ID', 'Not real work'],
  createdAt: '2026-11-04T06:00:00Z',
};

describe('WorkPhotoService', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('reads a page and maps the fields', async () => {
    const get = vi.spyOn(adminApiClient, 'get').mockResolvedValue({
      data: {
        items: [{ id: 'p1', shop_id: 's1', shop_name: 'Ravi', url: '/u', is_hidden: true, report_count: 3, report_reasons: ['x'], created_at: 'd' }],
        total: 30,
      },
    });
    const result = await service.getWorkPhotos('hidden', 2);
    expect(get).toHaveBeenCalledWith('/admin/work-photos', { params: { status: 'hidden', skip: 24, limit: 24 } });
    expect(result.total).toBe(30);
    expect(result.photos[0]).toMatchObject({ shopName: 'Ravi', isHidden: true, reportCount: 3, caption: null });
  });
});

describe('WorkPhotosPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    toast.mockReset();
    vi.spyOn(service, 'fetchPhotoFile').mockRejectedValue(new Error('no image in tests'));
  });

  it('shows who reported what, and starts with reported photos', async () => {
    const get = vi.spyOn(service, 'getWorkPhotos').mockResolvedValue({ photos: [photo], total: 1 });
    render(<WorkPhotosPage />);
    expect(await screen.findByText('Reported by 2 people')).toBeTruthy();
    expect(screen.getByText('Shows a customer ID')).toBeTruthy();
    expect(screen.getByText('New wiring')).toBeTruthy();
    expect(get).toHaveBeenCalledWith('reported', 1);
  });

  it('switches to hidden photos and offers to show them again', async () => {
    const get = vi.spyOn(service, 'getWorkPhotos').mockResolvedValue({ photos: [{ ...photo, isHidden: true }], total: 1 });
    render(<WorkPhotosPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Hidden' }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith('hidden', 1));
    expect(await screen.findByText('Hidden from customers')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Show again' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /^Hide$/ })).toBeNull();
  });

  it('keeps and hides, and says what happened', async () => {
    vi.spyOn(service, 'getWorkPhotos').mockResolvedValue({ photos: [photo], total: 1 });
    const set = vi.spyOn(service, 'setPhotoHidden').mockResolvedValue(photo);
    render(<WorkPhotosPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Keep' }));
    await waitFor(() => expect(set).toHaveBeenCalledWith('p1', false));
    fireEvent.click(await screen.findByRole('button', { name: /^Hide$/ }));
    await waitFor(() => expect(set).toHaveBeenCalledWith('p1', true));
    await waitFor(() => expect(toast).toHaveBeenCalledWith('Photo hidden; the owner has been told.'));
  });

  it('asks before removing for good', async () => {
    vi.spyOn(service, 'getWorkPhotos').mockResolvedValue({ photos: [photo], total: 1 });
    const remove = vi.spyOn(service, 'removePhoto').mockResolvedValue();
    render(<WorkPhotosPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Remove' }));
    expect(remove).not.toHaveBeenCalled();
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Remove photo' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('p1'));
  });

  it('says so when the list cannot load, or is empty', async () => {
    const get = vi.spyOn(service, 'getWorkPhotos').mockRejectedValueOnce({ response: { data: { detail: 'Not allowed' } } });
    const { unmount } = render(<WorkPhotosPage />);
    expect(await screen.findByRole('alert')).toBeTruthy();
    unmount();
    get.mockResolvedValue({ photos: [], total: 0 });
    render(<WorkPhotosPage />);
    expect(await screen.findByText('Nothing here.')).toBeTruthy();
  });
});
