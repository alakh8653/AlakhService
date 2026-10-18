import { useEffect, type ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Calendar, Scissors, Users, BarChart2, Settings, ListOrdered, Clock, Star, X } from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: <LayoutDashboard size={18} aria-hidden /> },
  { to: '/bookings', label: 'Bookings', icon: <Calendar size={18} aria-hidden /> },
  { to: '/queues', label: 'Queues', icon: <ListOrdered size={18} aria-hidden /> },
  { to: '/services', label: 'Services', icon: <Scissors size={18} aria-hidden /> },
  { to: '/staff', label: 'Staff', icon: <Users size={18} aria-hidden /> },
  { to: '/hours', label: 'Opening hours', icon: <Clock size={18} aria-hidden /> },
  { to: '/reviews', label: 'Reviews', icon: <Star size={18} aria-hidden /> },
  { to: '/analytics', label: 'Analytics', icon: <BarChart2 size={18} aria-hidden /> },
  { to: '/settings', label: 'Settings', icon: <Settings size={18} aria-hidden /> },
];

interface SidebarProps {
  /** Phone/tablet: whether the slide-in menu is showing. Always shown from the md breakpoint up. */
  open?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ open = false, onClose }: SidebarProps) {
  // Escape closes the phone menu.
  useEffect(() => {
    if (!open || !onClose) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-30 bg-gray-900/40 md:hidden" aria-hidden onClick={onClose} data-testid="nav-backdrop" />
      )}
      <aside
        id="main-nav"
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 flex flex-col h-full transition-transform md:static md:z-auto md:w-60 md:translate-x-0 ${
          open ? 'translate-x-0 shadow-xl' : '-translate-x-full'
        }`}
      >
        <div className="px-6 py-5 border-b border-gray-100 flex items-start justify-between">
          <div>
            <span className="text-lg font-bold text-indigo-600">AlakhService</span>
            <p className="text-xs text-gray-500 mt-0.5">Shop Dashboard</p>
          </div>
          {onClose && (
            <button type="button" onClick={onClose} aria-label="Close menu" className="md:hidden p-1 -mr-2 rounded-lg text-gray-500 hover:bg-gray-100">
              <X size={20} aria-hidden />
            </button>
          )}
        </div>
        <nav aria-label="Main" className="flex-1 py-4 space-y-1 px-3 overflow-y-auto">
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
                  isActive ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-50'
                }`
              }
            >
              {icon}
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
