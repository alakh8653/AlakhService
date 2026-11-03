import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ShopSetupPage from '../ShopSetupPage';

const createShop = vi.fn();
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: { name: 'Ravi' }, createShop, logout: vi.fn() }),
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <ShopSetupPage />
    </MemoryRouter>,
  );

const fillIn = (category: string) => {
  fireEvent.change(screen.getByLabelText('Shop name'), { target: { value: 'Ravi Works' } });
  fireEvent.change(screen.getByLabelText('City'), { target: { value: 'Pune' } });
  fireEvent.change(screen.getByLabelText('Category'), { target: { value: category } });
};

beforeEach(() => {
  createShop.mockReset();
  createShop.mockResolvedValue({ id: 's1' });
});

describe('ShopSetupPage', () => {
  it('lets a provider add another type of work', async () => {
    renderPage();
    expect(screen.queryByLabelText(/Other types of work/)).not.toBeInTheDocument();
    fillIn('electrical');
    fireEvent.change(screen.getByLabelText(/Other types of work/), { target: { value: 'plumbing' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create shop' }));
    await waitFor(() => expect(createShop).toHaveBeenCalled());
    expect(createShop.mock.calls[0][0]).toMatchObject({ category: 'electrical', extraCategories: ['plumbing'] });
  });

  it('can take a type away again, and a provider with one type adds none', async () => {
    renderPage();
    fillIn('electrical');
    fireEvent.change(screen.getByLabelText(/Other types of work/), { target: { value: 'plumbing' } });
    fireEvent.click(screen.getByRole('button', { name: 'Remove Plumbing' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create shop' }));
    await waitFor(() => expect(createShop).toHaveBeenCalled());
    expect(createShop.mock.calls[0][0]).toMatchObject({ category: 'electrical', extraCategories: [] });
  });

  it('stops offering more once a provider has as many as allowed', async () => {
    renderPage();
    fillIn('electrical');
    for (const type of ['plumbing', 'solar', 'welding', 'painting']) {
      fireEvent.change(screen.getByLabelText(/Other types of work/), { target: { value: type } });
    }
    expect(screen.queryByRole('combobox', { name: /Other types of work/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Remove Plumbing' })).toBeInTheDocument();
  });
});
