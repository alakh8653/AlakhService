import { beforeEach, describe, expect, it, vi } from 'vitest';
import { store } from '../../state/store';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import RegisterPage from '../RegisterPage';
import { register as registerAccount } from '../../services/authService';

const login = vi.fn();
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => ({ login }) }));
vi.mock('../../services/authService', () => ({ register: vi.fn() }));

const renderPage = () =>
  render(
    <Provider store={store}>
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    </Provider>,
  );

describe('RegisterPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('accepts a 10-digit mobile and the same password rules as the server', async () => {
    vi.mocked(registerAccount).mockResolvedValue({ id: 'u', name: 'Asha', email: 'a@x.in', phone: null, role: 'customer' });
    login.mockResolvedValue({});
    renderPage();
    fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Asha Rao' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'Asha@Example.com' } });
    fireEvent.change(screen.getByLabelText('Mobile (optional)'), { target: { value: '98765 43210' } });
    // No lowercase letter: the server allows it, so the form must too.
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'PASSWORD1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    await waitFor(() => expect(registerAccount).toHaveBeenCalled());
    expect(vi.mocked(registerAccount).mock.calls[0][0]).toMatchObject({ phone: '+919876543210', email: 'asha@example.com' });
    expect(login).toHaveBeenCalledWith({ email: 'asha@example.com', password: 'PASSWORD1' });
  });

  it('explains a weak password next to the field', async () => {
    renderPage();
    expect(screen.getByText('At least 8 characters, with a capital letter and a number.')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('Use at least 8 characters.')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toHaveAttribute('aria-invalid', 'true');
    expect(registerAccount).not.toHaveBeenCalled();
  });
});
