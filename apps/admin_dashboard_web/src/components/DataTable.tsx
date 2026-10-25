import type { KeyboardEvent, ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { formatNumber } from '../shared/format';

export interface Column<T> {
  key: keyof T & string;
  header: string;
  render?: (row: T) => ReactNode;
  /** Extra classes for the column's cells, e.g. `hidden lg:table-cell` to drop it on narrow screens. */
  className?: string;
}

interface DataTableProps<T extends { id: string }> {
  columns: Column<T>[];
  rows: T[];
  isLoading?: boolean;
  total?: number;
  /** The total is a lower bound (the API does not count): show "more available" instead of a page count. */
  totalIsEstimate?: boolean;
  page?: number;
  perPage?: number;
  onPageChange?: (page: number) => void;
  /** Opens a row; rows can then be reached with Tab and opened with Enter. */
  onRowClick?: (row: T) => void;
  /** Accessible name for a clickable row, e.g. "Open case 3820D121". */
  rowLabel?: (row: T) => string;
  emptyMessage?: ReactNode;
  /** Accessible name for the table. */
  label?: string;
}

export default function DataTable<T extends { id: string }>({
  columns,
  rows,
  isLoading = false,
  total = rows.length,
  totalIsEstimate = false,
  page = 1,
  perPage = rows.length || 1,
  onPageChange,
  onRowClick,
  rowLabel,
  emptyMessage = 'No records found.',
  label,
}: DataTableProps<T>) {
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  const first = (page - 1) * perPage + 1;
  const last = first + rows.length - 1;
  const hasNext = page < totalPages;

  const onRowKey = (e: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (e.target !== e.currentTarget) return; // a control inside the row
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onRowClick?.(row);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow overflow-hidden">
      <div className="overflow-x-auto">
        <table aria-label={label} aria-busy={isLoading || undefined} className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((col) => (
                <th key={col.key} scope="col" className={`px-4 py-3 font-semibold text-gray-600 whitespace-nowrap ${col.className?.includes('text-right') ? '' : 'text-left'} ${col.className ?? ''}`}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className={`divide-y divide-gray-100 transition-opacity ${isLoading && rows.length > 0 ? 'opacity-60' : ''}`}>
            {isLoading && rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-500">
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-500">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={onRowClick ? (e) => onRowKey(e, row) : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-label={onRowClick && rowLabel ? rowLabel(row) : undefined}
                  className={
                    onRowClick
                      ? 'cursor-pointer hover:bg-indigo-50 focus-visible:bg-indigo-50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-indigo-600'
                      : undefined
                  }
                >
                  {columns.map((col) => (
                    <td key={col.key} className={`px-4 py-3 text-gray-800 whitespace-nowrap ${col.className ?? ''}`}>
                      {col.render ? col.render(row) : String(row[col.key] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {onPageChange && (totalPages > 1 || page > 1) && (
        <nav aria-label="Pagination" className="flex items-center justify-between gap-3 px-4 py-3 border-t border-gray-100 text-sm text-gray-600">
          <span>
            {rows.length > 0 ? `Showing ${formatNumber(first)}–${formatNumber(last)}` : `Page ${page}`}
            {totalIsEstimate ? (hasNext ? ' · more available' : '') : ` of ${formatNumber(total)}`}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              aria-label="Previous page"
              disabled={page <= 1 || isLoading}
              onClick={() => onPageChange(page - 1)}
              className="p-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              type="button"
              aria-label="Next page"
              disabled={!hasNext || isLoading}
              onClick={() => onPageChange(page + 1)}
              className="p-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </nav>
      )}
    </div>
  );
}
