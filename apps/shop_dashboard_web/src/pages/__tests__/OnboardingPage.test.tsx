import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setShop } from '../../state/authSlice';
import bookingReducer from '../../state/bookingSlice';
import { ToastProvider } from '../../components/Toast';
import OnboardingBanner from '../../components/OnboardingBanner';
import OnboardingPage, { onboardingChecklist } from '../OnboardingPage';
import * as kyc from '../../services/kycService';
import { updateShop } from '../../services/shopService';
import type { Shop } from '../../types';

vi.mock('../../services/shopService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/shopService')>()),
  updateShop: vi.fn(),
}));

const shop: Shop = {
  id: 's1', ownerId: 'u1', name: 'Asha Salon', category: 'salon', description: null, city: 'Pune', address: null,
  phone: null, email: null, latitude: null, longitude: null, ratingAvg: 0, ratingCount: 0, isActive: true,
  isVerified: false, createdAt: '', verificationStatus: 'PENDING_REVIEW', rejectionReason: null, legalName: null,
  legalAddress: null, gstin: null, submittedAt: null,
};
const pan: kyc.ShopDocument = { id: 'd1', type: 'PAN', url: '/x', uploaded: true, fileName: 'pan.pdf', sizeBytes: 10, isVerified: false, createdAt: null };

function renderPage(s: Shop = shop) {
  const store = configureStore({ reducer: { auth: authReducer, bookings: bookingReducer } });
  store.dispatch(setShop(s));
  render(
    <Provider store={store}>
      <MemoryRouter>
        <ToastProvider>
          <OnboardingPage />
        </ToastProvider>
      </MemoryRouter>
    </Provider>,
  );
  return store;
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(updateShop).mockReset();
  vi.spyOn(kyc, 'getPayoutDetails').mockResolvedValue(null);
});

describe('onboarding checklist', () => {
  it('needs a legal name and PAN, and a GST certificate only with a GSTIN', () => {
    const required = (s: Shop, docs: kyc.ShopDocument[]) => onboardingChecklist(s, docs, false).filter((i) => i.required);
    expect(required(shop, []).map((i) => i.id)).toEqual(['legal', 'pan']);
    expect(required({ ...shop, gstin: '27AAPFU0939F1ZV' }, []).map((i) => i.id)).toEqual(['legal', 'pan', 'gst']);
    expect(required({ ...shop, legalName: 'Asha Pvt Ltd' }, [pan]).every((i) => i.done)).toBe(true);
  });
});

describe('OnboardingPage', () => {
  it('blocks submitting until the required items are done, then submits', async () => {
    vi.spyOn(kyc, 'getDocuments').mockResolvedValue([pan]);
    const submit = vi.spyOn(kyc, 'submitForReview').mockResolvedValue({ ...shop, legalName: 'Asha Pvt Ltd', submittedAt: '2026-10-22T00:00:00Z' });
    vi.mocked(updateShop).mockResolvedValue({ ...shop, legalName: 'Asha Pvt Ltd' });
    const store = renderPage();
    const button = await screen.findByRole('button', { name: 'Submit for review' });
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Legal business name'), { target: { value: 'Asha Pvt Ltd' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save business details' }));
    await waitFor(() => expect(updateShop).toHaveBeenCalledWith('s1', { legal_name: 'Asha Pvt Ltd', legal_address: null, gstin: null }));
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    await waitFor(() => expect(submit).toHaveBeenCalledWith('s1'));
    expect(await screen.findByText(/Submitted for review. We will tell you/)).toBeInTheDocument();
    expect(store.getState().auth.shop?.submittedAt).toBe('2026-10-22T00:00:00Z');
  });

  it('validates the GSTIN before saving', async () => {
    vi.spyOn(kyc, 'getDocuments').mockResolvedValue([]);
    renderPage();
    const input = await screen.findByLabelText('GSTIN (optional)');
    fireEvent.change(input, { target: { value: '27aapfu0939f1zw' } });
    expect(input).toHaveValue('27AAPFU0939F1ZW');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Save business details' }));
    expect(updateShop).not.toHaveBeenCalled();
  });

  it('uploads a document after checking the file', async () => {
    vi.spyOn(kyc, 'getDocuments').mockResolvedValue([]);
    const upload = vi.spyOn(kyc, 'uploadDocument').mockResolvedValue({ ...pan, type: 'GST', fileName: 'gst.pdf' });
    renderPage();
    const form = await screen.findByRole('form', { name: 'Upload a document' });
    fireEvent.change(within(form).getByLabelText('File'), { target: { files: [new File(['x'], 'a.exe', { type: 'application/x-msdownload' })] } });
    fireEvent.click(within(form).getByRole('button', { name: /Upload/ }));
    expect(await within(form).findByRole('alert')).toHaveTextContent('Choose a PDF, JPG, PNG or WebP file.');
    expect(upload).not.toHaveBeenCalled();

    const file = new File(['%PDF'], 'gst.pdf', { type: 'application/pdf' });
    fireEvent.change(within(form).getByLabelText('Document'), { target: { value: 'GST' } });
    fireEvent.change(within(form).getByLabelText('File'), { target: { files: [file] } });
    fireEvent.click(within(form).getByRole('button', { name: /Upload/ }));
    await waitFor(() => expect(upload).toHaveBeenCalledWith('s1', 'GST', file));
    expect(await screen.findByText('gst.pdf')).toBeInTheDocument();
  });

  it('shows why the shop was rejected and offers to submit again', async () => {
    vi.spyOn(kyc, 'getDocuments').mockResolvedValue([pan]);
    renderPage({ ...shop, verificationStatus: 'REJECTED', rejectionReason: 'PAN photo is blurred', legalName: 'Asha Pvt Ltd' });
    expect(await screen.findByText('PAN photo is blurred')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Submit again' })).toBeEnabled();
  });

  it('locks the verified legal details once approved', async () => {
    vi.spyOn(kyc, 'getDocuments').mockResolvedValue([{ ...pan, isVerified: true }]);
    renderPage({ ...shop, verificationStatus: 'APPROVED', isVerified: true, legalName: 'Asha Pvt Ltd' });
    expect(await screen.findByLabelText('Legal business name')).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Submit for review' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Remove PAN card' })).not.toBeInTheDocument();
  });

  it('shows an error when documents cannot load', async () => {
    vi.spyOn(kyc, 'getDocuments').mockRejectedValue({ response: { status: 503, data: { detail: 'Shop service unavailable' } } });
    renderPage();
    expect(await screen.findByText('Shop service unavailable')).toBeInTheDocument();
  });
});

describe('OnboardingBanner', () => {
  const renderBanner = (s: Shop) =>
    render(
      <MemoryRouter>
        <OnboardingBanner shop={s} />
      </MemoryRouter>,
    );

  it('explains the status with a link to verification, and hides once approved', () => {
    const { unmount } = renderBanner(shop);
    expect(screen.getByText(/not visible to customers yet/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Complete verification' })).toHaveAttribute('href', '/onboarding');
    unmount();
    const rejected = renderBanner({ ...shop, verificationStatus: 'REJECTED', rejectionReason: 'Blurred PAN' });
    expect(screen.getByText('Reason: Blurred PAN')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Fix and resubmit' })).toBeInTheDocument();
    rejected.unmount();
    const { container } = renderBanner({ ...shop, verificationStatus: 'APPROVED' });
    expect(container).toBeEmptyDOMElement();
  });
});
