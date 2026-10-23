import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import adminApiClient from '../../apiClient';
import { ToastProvider } from '../../components/Toast';
import PrivacyRequestsPage from '../PrivacyRequestsPage';
import * as service from '../PrivacyRequestService';

vi.mock('../../users/accountNames', () => ({
  useAccounts: () => ({ 'user-1': { id: 'user-1', name: 'Ravi Kumar', email: null, phone: null } }),
}));

const exportReq: service.PrivacyRequest = {
  id: 'e1', kind: 'export', userId: 'user-1', status: 'PENDING', reason: null, exportUrl: null,
  requestedAt: '2026-10-20T09:00:00Z', completedAt: null, resolutionNote: null,
};
const erasureReq: service.PrivacyRequest = { ...exportReq, id: 'r1', kind: 'erasure', reason: 'Leaving the app' };

describe('PrivacyRequestService', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('reads requests by status and records decisions', async () => {
    const get = vi.spyOn(adminApiClient, 'get').mockResolvedValue({
      data: { exports: [{ id: 'e1', user_id: 'u1', status: 'PENDING', requested_at: '2026-10-20T09:00:00Z' }], erasures: [] },
    });
    const res = await service.getPrivacyRequests('PENDING');
    expect(get).toHaveBeenCalledWith('/gdpr/admin/requests', { params: { status: 'PENDING', limit: 200 } });
    expect(res.exports[0]).toMatchObject({ id: 'e1', kind: 'export', userId: 'u1' });

    const post = vi.spyOn(adminApiClient, 'post').mockResolvedValue({ data: { id: 'e1', user_id: 'u1', status: 'COMPLETED', requested_at: 'x' } });
    await service.decideRequest({ id: 'e1', kind: 'export' }, { status: 'COMPLETED', exportUrl: 'https://x.example/d.zip' });
    expect(post).toHaveBeenCalledWith('/gdpr/admin/export/e1/decision', { status: 'COMPLETED', note: undefined, export_url: 'https://x.example/d.zip' });
    await service.decideRequest({ id: 'r1', kind: 'erasure' }, { status: 'REJECTED', note: 'Tax records', exportUrl: 'https://ignored' });
    expect(post).toHaveBeenLastCalledWith('/gdpr/admin/erasure/r1/decision', { status: 'REJECTED', note: 'Tax records', export_url: undefined });
  });
});

describe('PrivacyRequestsPage', () => {
  beforeEach(() => vi.restoreAllMocks());

  const renderPage = () =>
    render(
      <ToastProvider>
        <PrivacyRequestsPage />
      </ToastProvider>,
    );

  it('lists pending exports and erasures and completes an export with a download link', async () => {
    vi.spyOn(service, 'getPrivacyRequests').mockResolvedValue({ exports: [exportReq], erasures: [erasureReq] });
    const decide = vi.spyOn(service, 'decideRequest').mockResolvedValue({ ...exportReq, status: 'COMPLETED' });
    renderPage();
    const erasures = await screen.findByRole('table', { name: 'Account erasures' });
    expect(await within(erasures).findByText('Leaving the app')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Complete export request from Ravi Kumar' }));
    const dialog = screen.getByRole('dialog');
    const submit = within(dialog).getByRole('button', { name: 'Mark completed' });
    fireEvent.change(within(dialog).getByLabelText(/Download link/), { target: { value: 'http://insecure' } });
    expect(submit).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText(/Download link/), { target: { value: 'https://files.example/u1.zip' } });
    fireEvent.click(submit);
    await waitFor(() => expect(decide).toHaveBeenCalledWith(exportReq, { status: 'COMPLETED', exportUrl: 'https://files.example/u1.zip', note: '' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Complete export request from Ravi Kumar' })).not.toBeInTheDocument());
  });

  it('rejects with a reason and switches status', async () => {
    const get = vi.spyOn(service, 'getPrivacyRequests').mockResolvedValue({ exports: [], erasures: [erasureReq] });
    const decide = vi.spyOn(service, 'decideRequest').mockResolvedValue({ ...erasureReq, status: 'REJECTED' });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Reject erasure request from Ravi Kumar' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: 'Open dispute' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject request' }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith(erasureReq, { status: 'REJECTED', note: 'Open dispute' }));

    fireEvent.click(screen.getByRole('button', { name: 'Completed' }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith('COMPLETED'));
  });

  it('shows an error when the requests cannot load', async () => {
    vi.spyOn(service, 'getPrivacyRequests').mockRejectedValue(new Error('down'));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load privacy requests.');
  });
});
