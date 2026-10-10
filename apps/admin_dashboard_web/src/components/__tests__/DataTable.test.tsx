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

  it('calls onRowClick with the clicked row', () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={columns} rows={rows} onRowClick={onRowClick} />);
    fireEvent.click(screen.getByText('Beta'));
    expect(onRowClick).toHaveBeenCalledWith(rows[1]);
  });

  it('paginates and disables the edge buttons', () => {
    const onPageChange = vi.fn();
    render(<DataTable columns={columns} rows={rows} total={50} page={1} perPage={20} onPageChange={onPageChange} />);
    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument();
    expect(screen.getByLabelText('Previous page')).toBeDisabled();
    fireEvent.click(screen.getByLabelText('Next page'));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });
});
