import React, { useEffect, useState } from 'react';
import apiClient from '../services/apiClient';
import type { Service } from '../types';
import { Plus, Edit2, ToggleLeft, ToggleRight } from 'lucide-react';

export default function ServicesPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    apiClient.get<{ data: Service[] }>('/services').then(({ data }) => {
      setServices(data.data);
    }).finally(() => setIsLoading(false));
  }, []);

  const toggleActive = async (service: Service) => {
    const { data } = await apiClient.patch<{ data: Service }>(`/services/${service.id}`, { isActive: !service.isActive });
    setServices((prev) => prev.map((s) => (s.id === service.id ? data.data : s)));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Services</h1>
        <button className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">
          <Plus size={16} /> Add Service
        </button>
      </div>
      {isLoading ? <p className="text-gray-500">Loading services…</p> : (
        <div className="bg-white rounded-2xl shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left">Service</th>
                <th className="px-4 py-3 text-left">Category</th>
                <th className="px-4 py-3 text-right">Duration</th>
                <th className="px-4 py-3 text-right">Price</th>
                <th className="px-4 py-3 text-center">Active</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {services.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{s.name}</td>
                  <td className="px-4 py-3 text-gray-500">{s.category}</td>
                  <td className="px-4 py-3 text-right text-gray-500">{s.durationMinutes} min</td>
                  <td className="px-4 py-3 text-right font-medium">${s.price}</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActive(s)} className={s.isActive ? 'text-green-500' : 'text-gray-400'}>
                      {s.isActive ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button className="text-indigo-500 hover:text-indigo-700"><Edit2 size={16} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
