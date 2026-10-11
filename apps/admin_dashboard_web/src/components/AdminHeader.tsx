import { LogOut } from 'lucide-react';
import { signOut } from '../auth/session';

export default function AdminHeader() {
  const handleLogout = () => {
    signOut();
    window.location.assign('/login');
  };

  return (
    <header className="h-16 shrink-0 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <span className="text-sm text-gray-500">{import.meta.env.VITE_APP_TITLE ?? 'AlakhService Admin Dashboard'}</span>
      <button
        type="button"
        onClick={handleLogout}
        className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
      >
        <LogOut size={16} /> Sign out
      </button>
    </header>
  );
}
