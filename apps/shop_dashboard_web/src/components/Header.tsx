import React from 'react';
import { Bell, LogOut } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export default function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 flex-shrink-0">
      <p className="text-sm text-gray-500">
        Welcome back, <span className="font-semibold text-gray-900">{user?.name ?? '…'}</span>
      </p>
      <div className="flex items-center gap-4">
        <button className="relative text-gray-500 hover:text-gray-800">
          <Bell size={20} />
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center">3</span>
        </button>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-sm font-semibold text-indigo-600">
            {user?.name?.charAt(0) ?? '?'}
          </div>
          <span className="text-sm font-medium text-gray-700 hidden sm:block">{user?.name}</span>
        </div>
        <button onClick={logout} title="Sign out" className="text-gray-400 hover:text-red-500">
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
