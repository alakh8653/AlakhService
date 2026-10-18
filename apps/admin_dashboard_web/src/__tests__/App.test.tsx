import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

vi.mock('../auth/session', () => ({ isSignedIn: () => true, signOut: vi.fn() }));

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );

describe('App shell', () => {
  it('shows a way back from an unknown address instead of a blank page', async () => {
    renderAt('/nowhere');
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go to Disputes' })).toHaveAttribute('href', '/disputes');
  });

  it('opens the menu drawer from the header and closes it with Escape or by choosing a page', async () => {
    renderAt('/nowhere');
    const menu = screen.getByRole('button', { name: 'Open menu' });
    expect(menu).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(menu);
    expect(menu).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: 'Close menu' })).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(menu).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(menu);
    fireEvent.click(screen.getByRole('link', { name: 'Roles' }));
    expect(menu).toHaveAttribute('aria-expanded', 'false');
  });

  it('names the browser tab after the page', async () => {
    renderAt('/disputes/abc');
    await waitFor(() => expect(document.title).toBe('Disputes · AlakhService Admin'));
    renderAt('/finance/coupons');
    await waitFor(() => expect(document.title).toBe('Coupons · AlakhService Admin'));
  });

  it('offers a skip link to the main content', () => {
    renderAt('/nowhere');
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main');
  });
});
