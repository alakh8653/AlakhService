import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ProviderProfileCard from '../ProviderProfileCard';
import ExtraChargeDialog from '../ExtraChargeDialog';
import * as service from '../../services/profileService';

const toast = vi.fn();
vi.mock('../Toast', () => ({ useToast: () => toast }));

const profile: service.ProviderProfile = {
  yearsExperience: 9,
  languages: ['Hindi'],
  photos: [{ id: 'p1', url: 'http://x/p1', caption: 'New wiring', isHidden: true }],
};

describe('ProviderProfileCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    toast.mockReset();
    vi.spyOn(service, 'getProfile').mockResolvedValue(profile);
  });

  it('shows what was saved, and marks a hidden photo', async () => {
    render(<ProviderProfileCard shopId="s1" />);
    expect(((await screen.findByLabelText('Years of experience')) as HTMLInputElement).value).toBe('9');
    expect((screen.getByLabelText('Hindi') as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText('Hidden while we check')).toBeTruthy();
  });

  it('saves experience and languages', async () => {
    const save = vi.spyOn(service, 'saveProfile').mockResolvedValue();
    render(<ProviderProfileCard shopId="s1" />);
    fireEvent.change(await screen.findByLabelText('Years of experience'), { target: { value: '12' } });
    fireEvent.click(screen.getByLabelText('Tamil'));
    fireEvent.click(screen.getByRole('button', { name: 'Save profile' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith('s1', 12, ['Hindi', 'Tamil']));
    expect(toast).toHaveBeenCalledWith('Saved. Customers can see this.');
  });

  it('refuses a silly number without sending it', async () => {
    const save = vi.spyOn(service, 'saveProfile').mockResolvedValue();
    render(<ProviderProfileCard shopId="s1" />);
    fireEvent.change(await screen.findByLabelText('Years of experience'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save profile' }));
    expect((await screen.findByRole('alert')).textContent).toContain('0 to 70');
    expect(save).not.toHaveBeenCalled();
  });

  it('uploads a photo, and refuses a PDF or one that is too large', async () => {
    const add = vi.spyOn(service, 'addPhoto').mockResolvedValue();
    render(<ProviderProfileCard shopId="s1" />);
    const input = await screen.findByLabelText('Add a photo');
    fireEvent.change(input, { target: { files: [new File(['x'], 'a.pdf', { type: 'application/pdf' })] } });
    expect((await screen.findByRole('alert')).textContent).toContain('JPEG');
    const big = new File(['x'], 'b.jpg', { type: 'image/jpeg' });
    Object.defineProperty(big, 'size', { value: 6 * 1024 * 1024 });
    fireEvent.change(input, { target: { files: [big] } });
    expect((await screen.findByRole('alert')).textContent).toContain('too large');
    expect(add).not.toHaveBeenCalled();
    const good = new File(['x'], 'c.jpg', { type: 'image/jpeg' });
    fireEvent.change(input, { target: { files: [good] } });
    await waitFor(() => expect(add).toHaveBeenCalledWith('s1', good));
  });

  it('removes a photo', async () => {
    const remove = vi.spyOn(service, 'removePhoto').mockResolvedValue();
    render(<ProviderProfileCard shopId="s1" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Remove photo New wiring' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('s1', 'p1'));
  });
});

describe('ExtraChargeDialog', () => {
  it('needs a reason and a whole number, then sends paise', async () => {
    const onConfirm = vi.fn().mockResolvedValue(true);
    const onClose = vi.fn();
    render(<ExtraChargeDialog bookingNumber="BK1" onConfirm={onConfirm} onClose={onClose} />);
    expect(screen.getByText(/must approve/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Send to customer' }));
    expect((await screen.findByRole('alert')).textContent).toContain('what it is for');
    fireEvent.click(screen.getByLabelText('Spare parts'));
    fireEvent.click(screen.getByRole('button', { name: 'Send to customer' }));
    expect((await screen.findByRole('alert')).textContent).toContain('whole rupees');
    fireEvent.change(screen.getByLabelText('How much more (₹)'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send to customer' }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith(20000, 'Spare parts'));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('stays open when it could not be sent', async () => {
    const onClose = vi.fn();
    render(<ExtraChargeDialog bookingNumber="BK1" onConfirm={vi.fn().mockResolvedValue(false)} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText('Extra work'));
    fireEvent.change(screen.getByLabelText('How much more (₹)'), { target: { value: '50' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send to customer' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Send to customer' })).toBeTruthy());
    expect(onClose).not.toHaveBeenCalled();
  });
});
