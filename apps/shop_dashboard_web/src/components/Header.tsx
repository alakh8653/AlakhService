import { LogOut, Store } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export default function Header() {
  const { user, shop, logout } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 flex-shrink-0">
      <p className="text-sm text-gray-500 flex items-center gap-2">
        <Store size={16} className="text-gray-400" />
        <span className="font-semibold text-gray-900">{shop?.name ?? '…'}</span>
        {shop && !shop.isVerified && (
          <span className="text-xs bg-yellow-100 text-yellow-800 rounded-full px-2 py-0.5">Pending verification</span>
        )}
      </p>
      <div className="flex items-center gap-4">
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
