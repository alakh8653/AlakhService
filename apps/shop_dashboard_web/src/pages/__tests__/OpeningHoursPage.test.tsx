import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setShop } from '../../state/authSlice';
import bookingReducer from '../../state/bookingSlice';
import OpeningHoursPage from '../OpeningHoursPage';
import { ToastProvider } from '../../components/Toast';
import { addHoliday, getShopHours, removeHoliday, saveCapacity, saveWeeklyHours } from '../../services/shopService';
import type { OpenInterval, Shop, ShopHours } from '../../types';

vi.mock('../../services/shopService', () => ({
  getShopHours: vi.fn(),
  saveWeeklyHours: vi.fn(),
  saveCapacity: vi.fn(),
  addHoliday: vi.fn(),
  removeHoliday: vi.fn(),
}));

const closed = (): OpenInterval[][] => Array.from({ length: 7 }, () => []);
const hours = (over: Partial<ShopHours> = {}): ShopHours => ({
  configured: false,
  timezone: 'Asia/Kolkata',
  weekly: closed(),
  holidays: [],
  capacity: 2,
  capacityOverride: null,
  activeStaff: 2,
  updatedAt: null,
  ...over,
});

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer, bookings: bookingReducer } });
  store.dispatch(setShop({ id: 's1', name: 'Asha Salon' } as Shop));
  render(
    <Provider store={store}>
      <ToastProvider>
        <OpeningHoursPage />
      </ToastProvider>
    </Provider>,
  );
}

const savedWeek = () => vi.mocked(saveWeeklyHours).mock.calls[0][1];
const field = (name: string) => screen.getByLabelText(name) as HTMLInputElement;
const change = (name: string, value: string) => fireEvent.change(field(name), { target: { value } });
const save = () => fireEvent.click(screen.getByRole('button', { name: 'Save hours' }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(saveWeeklyHours).mockImplementation(async (_id, weekly) => hours({ configured: true, weekly }));
});

describe('OpeningHoursPage weekly hours', () => {
  it('starts a shop without hours from Monday to Saturday, 10 to 8, and publishes them on save', async () => {
    vi.mocked(getShopHours).mockResolvedValue(hours());
    renderPage();
    expect(await screen.findByText(/haven't published opening hours yet/)).toBeInTheDocument();
    expect(field('Monday opens')).toHaveValue('10:00');
    expect(field('Saturday closes')).toHaveValue('20:00');
    expect(screen.getByRole('switch', { name: 'Open on Sunday' })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByText('Not published yet')).toBeInTheDocument();

    save();
    await waitFor(() => expect(saveWeeklyHours).toHaveBeenCalled());
    expect(savedWeek()).toEqual([...Array(6).fill([{ start: '10:00', end: '20:00' }]), []]);
    expect(await screen.findByText(/Opening hours saved/)).toBeInTheDocument();
    expect(screen.queryByText(/haven't published/)).not.toBeInTheDocument();
  });

  it('adds a second shift after lunch and copies Monday to the other weekdays', async () => {
    vi.mocked(getShopHours).mockResolvedValue(hours({ configured: true, weekly: [[{ start: '10:00', end: '14:00' }], ...closed().slice(1)] }));
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Add hours (e.g. after a lunch break) on Monday' }));
    change('Monday opens (2)', '16:00');
    change('Monday closes (2)', '20:00');
    fireEvent.click(screen.getByRole('button', { name: 'Copy Monday to all weekdays' }));
    expect(field('Friday closes (2)')).toHaveValue('20:00');
    expect(screen.getByRole('switch', { name: 'Open on Saturday' })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();

    save();
    await waitFor(() => expect(saveWeeklyHours).toHaveBeenCalled());
    const split = [{ start: '10:00', end: '14:00' }, { start: '16:00', end: '20:00' }];
    expect(savedWeek()).toEqual([split, split, split, split, split, [], []]);
  });

  it('says what is wrong with a day and saves nothing', async () => {
    vi.mocked(getShopHours).mockResolvedValue(hours());
    renderPage();
    await screen.findByLabelText('Monday closes');
    change('Monday closes', '09:00');
    save();
    expect(await screen.findByText('Monday: Opening time 10:00 AM must be before closing time 9:00 AM')).toBeInTheDocument();
    expect(field('Monday closes')).toHaveAttribute('aria-invalid', 'true');

    change('Monday closes', '14:00');
    fireEvent.click(screen.getByRole('button', { name: 'Add hours (e.g. after a lunch break) on Monday' }));
    change('Monday opens (2)', '13:00');
    expect(screen.getByText('Monday: These hours overlap or touch; merge them into one')).toBeInTheDocument();
    change('Monday opens (2)', '16:10');
    expect(screen.getByText('Monday: Use times on the quarter hour (:00, :15, :30 or :45)')).toBeInTheDocument();
    expect(saveWeeklyHours).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Remove Monday hours 2' }));
    save();
    await waitFor(() => expect(saveWeeklyHours).toHaveBeenCalled());
    expect(savedWeek()[0]).toEqual([{ start: '10:00', end: '14:00' }]);
  });

  it('closes a day with its switch, remembers its hours, and keeps midnight closing as 24:00', async () => {
    vi.mocked(getShopHours).mockResolvedValue(
      hours({ configured: true, weekly: [[{ start: '09:00', end: '13:00' }], [], [], [], [], [{ start: '18:00', end: '24:00' }], []] }),
    );
    renderPage();
    expect(await screen.findByLabelText('Saturday closes')).toHaveValue('00:00');
    const monday = screen.getByRole('switch', { name: 'Open on Monday' });
    fireEvent.click(monday);
    expect(screen.queryByLabelText('Monday opens')).not.toBeInTheDocument();
    fireEvent.click(monday);
    expect(field('Monday opens')).toHaveValue('09:00'); // switched back on with the same hours
    fireEvent.click(monday);

    save();
    await waitFor(() => expect(saveWeeklyHours).toHaveBeenCalled());
    expect(savedWeek()[0]).toEqual([]);
    expect(savedWeek()[5]).toEqual([{ start: '18:00', end: '24:00' }]);
  });

  it('shows why the server refused the hours', async () => {
    vi.mocked(getShopHours).mockResolvedValue(hours());
    vi.mocked(saveWeeklyHours).mockRejectedValue({ response: { data: { detail: 'Not your shop' } } });
    renderPage();
    await screen.findByLabelText('Monday opens');
    save();
    expect(await screen.findByRole('alert')).toHaveTextContent('Not your shop');
  });

  it('offers to try again when the hours could not be loaded', async () => {
    vi.mocked(getShopHours).mockRejectedValueOnce(new Error('Network Error')).mockResolvedValueOnce(hours());
    renderPage();
    expect(await screen.findByText('Network Error')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByLabelText('Monday opens')).toBeInTheDocument();
  });
});

describe('OpeningHoursPage closures and capacity', () => {
  it('adds a closure with a note and removes it again', async () => {
    vi.mocked(getShopHours).mockResolvedValue(hours({ configured: true }));
    vi.mocked(addHoliday).mockImplementation(async (_id, date, note) => hours({ configured: true, holidays: [{ date, note }] }));
    vi.mocked(removeHoliday).mockResolvedValue();
    renderPage();
    expect(await screen.findByText('No upcoming closures.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Add closure/ }));
    expect(screen.getByText('Choose the date you will be closed')).toBeInTheDocument();
    change('Date', '2020-01-01');
    fireEvent.click(screen.getByRole('button', { name: /Add closure/ }));
    expect(screen.getByText('That date has already passed')).toBeInTheDocument();

    change('Date', '2099-11-08');
    change('Note (optional)', 'Diwali');
    fireEvent.click(screen.getByRole('button', { name: /Add closure/ }));
    await waitFor(() => expect(addHoliday).toHaveBeenCalledWith('s1', '2099-11-08', 'Diwali'));
    const list = await screen.findByRole('list', { name: 'Upcoming closures' });
    expect(within(list).getByText('Diwali')).toBeInTheDocument();
    expect(await screen.findByText(/Customers can't book that day/)).toBeInTheDocument();

    fireEvent.click(within(list).getByRole('button', { name: /Remove/ }));
    await waitFor(() => expect(removeHoliday).toHaveBeenCalledWith('s1', '2099-11-08'));
    expect(await screen.findByText('No upcoming closures.')).toBeInTheDocument();
  });

  it('explains the default capacity, saves an override and goes back to the staff count', async () => {
    vi.mocked(getShopHours).mockResolvedValue(hours({ configured: true, capacity: 2, activeStaff: 2 }));
    vi.mocked(saveCapacity).mockImplementation(async (_id, capacity) =>
      hours({ configured: true, capacity: capacity ?? 2, capacityOverride: capacity, activeStaff: 2 }),
    );
    renderPage();
    expect(await screen.findByText(/one per active staff member \(2 people\)/)).toBeInTheDocument();
    expect(field('Customers at once')).toHaveValue(2);
    expect(screen.queryByRole('button', { name: /Use staff count/ })).not.toBeInTheDocument();

    change('Customers at once', '0');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(screen.getByText('Enter a whole number from 1 to 100')).toBeInTheDocument();
    expect(saveCapacity).not.toHaveBeenCalled();

    change('Customers at once', '4');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(saveCapacity).toHaveBeenCalledWith('s1', 4));
    expect(await screen.findByText('Up to 4 customers can now book the same time.')).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: 'Use staff count (2)' }));
    await waitFor(() => expect(saveCapacity).toHaveBeenLastCalledWith('s1', null));
    await waitFor(() => expect(field('Customers at once')).toHaveValue(2));
  });
});
