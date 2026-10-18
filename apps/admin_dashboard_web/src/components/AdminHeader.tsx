import { LogOut, Menu } from 'lucide-react';
import { signOut } from '../auth/session';

export default function AdminHeader({ onOpenMenu, menuOpen }: { onOpenMenu: () => void; menuOpen: boolean }) {
  const handleLogout = () => {
    signOut();
    window.location.assign('/login');
  };

  return (
    <header className="h-16 shrink-0 bg-white border-b border-gray-200 flex items-center justify-between gap-3 px-4 sm:px-6">
      <div className="flex items-center gap-2 min-w-0">
        <button
          type="button"
          aria-label="Open menu"
          aria-controls="admin-sidebar"
          aria-expanded={menuOpen}
          onClick={onOpenMenu}
          className="lg:hidden p-2 -ml-2 rounded-lg text-gray-700 hover:bg-gray-100"
        >
          <Menu size={20} />
        </button>
        <span className="text-sm text-gray-600 truncate">{import.meta.env.VITE_APP_TITLE ?? 'AlakhService Admin Dashboard'}</span>
      </div>
      <button
        type="button"
        onClick={handleLogout}
        className="shrink-0 flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 rounded-lg px-2 py-1"
      >
        <LogOut size={16} aria-hidden="true" /> Sign out
      </button>
    </header>
  );
}
