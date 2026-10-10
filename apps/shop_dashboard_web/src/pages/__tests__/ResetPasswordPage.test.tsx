import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ResetPasswordPage, { passwordProblem } from '../ResetPasswordPage';
import { confirmPasswordReset } from '../../services/authService';

vi.mock('../../services/authService', () => ({ confirmPasswordReset: vi.fn() }));

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <ResetPasswordPage />
    </MemoryRouter>,
  );

describe('ResetPasswordPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('applies the same password rules as the server', () => {
    expect(passwordProblem('Short1')).toMatch(/8 characters/);
    expect(passwordProblem('lowercase1')).toMatch(/uppercase/);
    expect(passwordProblem('NoDigitsHere')).toMatch(/digit/);
    expect(passwordProblem('NewPassword1')).toBeNull();
  });

  it('sends the token from the link with the new password', async () => {
    vi.mocked(confirmPasswordReset).mockResolvedValue();
    renderAt('/reset-password?token=abc.def');
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'NewPassword1' } });
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'NewPassword1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(await screen.findByText(/password has been changed/)).toBeInTheDocument();
    expect(confirmPasswordReset).toHaveBeenCalledWith('abc.def', 'NewPassword1');
  });

  it('rejects mismatched passwords without calling the server', () => {
    renderAt('/reset-password?token=abc');
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'NewPassword1' } });
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'Different1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(screen.getByText('The passwords do not match.')).toBeInTheDocument();
    expect(confirmPasswordReset).not.toHaveBeenCalled();
  });

  it('explains an incomplete link', () => {
    renderAt('/reset-password');
    expect(screen.getByText(/link is incomplete/)).toBeInTheDocument();
  });
});
