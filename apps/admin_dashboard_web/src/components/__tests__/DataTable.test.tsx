import { fireEvent, render, screen } from '@testing-library/react';
import DataTable, { type Column } from '../DataTable';

interface Row {
  id: string;
  name: string;
  count: number;
}

const columns: Column<Row>[] = [
  { key: 'name', header: 'Name' },
  { key: 'count', header: 'Count', render: (r) => `${r.count} items` },
];

const rows: Row[] = [
  { id: '1', name: 'Alpha', count: 3 },
  { id: '2', name: 'Beta', count: 5 },
];

describe('DataTable', () => {
  it('renders headers and rows, using custom renderers', () => {
    render(<DataTable columns={columns} rows={rows} />);
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('5 items')).toBeInTheDocument();
  });

  it('shows the loading and empty states', () => {
    const { rerender } = render(<DataTable columns={columns} rows={[]} isLoading />);
    expect(screen.getByText('Loading…')).toBeInTheDocument();
    rerender(<DataTable columns={columns} rows={[]} />);
    expect(screen.getByText('No records found.')).toBeInTheDocument();
  });

  it('does not claim the list is empty when loading failed', () => {
    render(<DataTable columns={columns} rows={[]} emptyMessage="No disputes have been raised yet." failed />);
    expect(screen.getByText('Could not load this list.')).toBeInTheDocument();
    expect(screen.queryByText('No disputes have been raised yet.')).not.toBeInTheDocument();
  });

  it('calls onRowClick with the clicked row', () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={columns} rows={rows} onRowClick={onRowClick} />);
    fireEvent.click(screen.getByText('Beta'));
    expect(onRowClick).toHaveBeenCalledWith(rows[1]);
  });

  it('paginates and disables the edge buttons', () => {
    const onPageChange = vi.fn();
    render(<DataTable columns={columns} rows={rows} total={50} page={1} perPage={20} onPageChange={onPageChange} />);
    expect(screen.getByText('Showing 1–2 of 50')).toBeInTheDocument();
    expect(screen.getByLabelText('Previous page')).toBeDisabled();
    fireEvent.click(screen.getByLabelText('Next page'));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('opens a row from the keyboard', () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={columns} rows={rows} onRowClick={onRowClick} rowLabel={(r) => `Open ${r.name}`} />);
    const row = screen.getByRole('row', { name: 'Open Alpha' });
    expect(row).toHaveAttribute('tabindex', '0');
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(onRowClick).toHaveBeenCalledWith(rows[0]);
  });

  it('keeps the current rows visible while the next page loads', () => {
    render(<DataTable columns={columns} rows={rows} isLoading />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.queryByText('Loading…')).not.toBeInTheDocument();
    expect(screen.getByRole('table')).toHaveAttribute('aria-busy', 'true');
  });

  it('says "more available" instead of a made-up total when the API does not count', () => {
    render(<DataTable columns={columns} rows={rows} total={3} totalIsEstimate page={1} perPage={2} onPageChange={vi.fn()} />);
    expect(screen.getByText('Showing 1–2 · more available')).toBeInTheDocument();
  });
});
