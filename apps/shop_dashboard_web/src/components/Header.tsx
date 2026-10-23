import { LogOut, Menu, Store } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { verificationOf } from '../services/shopService';

export default function Header({ onOpenMenu, menuOpen = false }: { onOpenMenu?: () => void; menuOpen?: boolean }) {
  const { user, shop, logout } = useAuth();

  return (
    <header className="h-14 md:h-16 bg-white border-b border-gray-200 flex items-center justify-between gap-2 px-3 md:px-6 flex-shrink-0">
      <div className="flex items-center gap-2 min-w-0">
        {onOpenMenu && (
          <button
            type="button"
            onClick={onOpenMenu}
            aria-label="Open menu"
            aria-controls="main-nav"
            aria-expanded={menuOpen}
            className="md:hidden p-2 -ml-1 rounded-lg text-gray-600 hover:bg-gray-100"
          >
            <Menu size={22} aria-hidden />
          </button>
        )}
        <p className="text-sm text-gray-500 flex items-center gap-2 min-w-0">
          <Store size={16} className="text-gray-400 flex-shrink-0 hidden sm:block" aria-hidden />
          <span className="font-semibold text-gray-900 truncate">{shop?.name ?? '…'}</span>
          {shop && verificationOf(shop) === 'PENDING_REVIEW' && (
            <span
              className="text-xs bg-yellow-100 text-yellow-800 rounded-full px-2 py-0.5 whitespace-nowrap"
              title="Customers cannot see your shop until our team has verified it."
            >
              <span className="sm:hidden">Unverified</span>
              <span className="hidden sm:inline">Pending verification</span>
            </span>
          )}
          {shop && verificationOf(shop) === 'REJECTED' && (
            <span className="text-xs bg-red-100 text-red-800 rounded-full px-2 py-0.5 whitespace-nowrap">Not approved</span>
          )}
        </p>
      </div>
      <div className="flex items-center gap-2 md:gap-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-sm font-semibold text-indigo-600" aria-hidden>
            {user?.name?.charAt(0) ?? '?'}
          </div>
          <span className="text-sm font-medium text-gray-700 hidden sm:block">{user?.name}</span>
        </div>
        <button
          type="button"
          onClick={() => void logout()}
          aria-label="Sign out"
          title="Sign out"
          className="p-2 rounded-lg text-gray-500 hover:text-red-600 hover:bg-red-50"
        >
          <LogOut size={18} aria-hidden />
        </button>
      </div>
    </header>
  );
}
