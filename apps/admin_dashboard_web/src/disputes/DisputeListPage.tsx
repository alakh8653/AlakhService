import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { getDisputes, type Dispute, type DisputeStatus } from './DisputeService';
import DataTable, { type Column } from '../components/DataTable';

const STATUS_COLORS: Record<DisputeStatus, string> = {
  open: 'bg-red-100 text-red-800',
  under_review: 'bg-yellow-100 text-yellow-800',
  resolved: 'bg-green-100 text-green-800',
  closed: 'bg-gray-100 text-gray-700',
};

export default function DisputeListPage() {
  const navigate = useNavigate();
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<DisputeStatus | undefined>();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    getDisputes({ status: statusFilter, page, perPage: 20 })
      .then((res) => { setDisputes(res.data); setTotal(res.total); })
      .finally(() => setIsLoading(false));
  }, [statusFilter, page]);

  const columns: Column<Dispute>[] = [
    { key: 'caseNumber', header: 'Case #' },
    { key: 'customerName', header: 'Customer' },
    { key: 'shopName', header: 'Shop' },
    { key: 'reason', header: 'Reason' },
    {
      key: 'status',
      header: 'Status',
      render: (r) => (
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[r.status]}`}>
          {r.status.replace('_', ' ')}
        </span>
      ),
    },
    { key: 'createdAt', header: 'Opened', render: (r) => format(new Date(r.createdAt), 'MMM d, yyyy') },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Disputes</h1>
      <div className="flex gap-2 flex-wrap">
        {(['open', 'under_review', 'resolved', 'closed'] as DisputeStatus[]).map((s) => (
          <button key={s} onClick={() => setStatusFilter(s === statusFilter ? undefined : s)}
            className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${statusFilter === s ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}>
            {s.replace('_', ' ')}
          </button>
        ))}
      </div>
      <DataTable columns={columns} rows={disputes} isLoading={isLoading} total={total} page={page} perPage={20} onPageChange={setPage}
        onRowClick={(row) => navigate(`/disputes/${row.id}`)} />
    </div>
  );
}
