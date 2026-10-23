import { useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  FileClock,
  Gauge,
  KeyRound,
  MessageSquareWarning,
  Scale,
  Store,
  UserLock,
  ShieldCheck,
  Wallet,
  TicketPercent,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Operations',
    items: [
      { to: '/users', label: 'Users', icon: Users },
      { to: '/shops', label: 'Shops', icon: Store },
      { to: '/audit', label: 'Audit Logs', icon: FileClock },
      { to: '/disputes', label: 'Disputes', icon: Scale },
      { to: '/moderation/contact-sharing', label: 'Contact Sharing', icon: MessageSquareWarning },
      { to: '/privacy-requests', label: 'Privacy requests', icon: UserLock },
    ],
  },
  {
    title: 'Finance',
    items: [
      { to: '/finance/settlements', label: 'Settlements', icon: Wallet },
      { to: '/finance/revenue', label: 'Revenue Report', icon: BarChart3 },
      { to: '/finance/coupons', label: 'Coupons', icon: TicketPercent },
    ],
  },
  {
    title: 'Monitoring',
    items: [
      { to: '/monitoring/health', label: 'System Health', icon: Activity },
      { to: '/monitoring/metrics', label: 'Service Metrics', icon: Gauge },
    ],
  },
  {
    title: 'Access Control',
    items: [
      { to: '/access/roles', label: 'Roles', icon: ShieldCheck },
      { to: '/access/permissions', label: 'Permissions', icon: KeyRound },
    ],
  },
];

/** The nav label for a path ("/disputes/123" → "Disputes"), for the page title. */
export function navLabelFor(pathname: string): string | undefined {
  const items = NAV_SECTIONS.flatMap((s) => s.items);
  return items.find((i) => pathname === i.to || pathname.startsWith(`${i.to}/`))?.label;
}

/**
 * Always visible on wide screens; below `lg` it is a drawer opened from the header's menu button,
 * closed by Escape, the backdrop, the close button or choosing a page.
 */
export default function AdminSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-gray-900/50 lg:hidden" aria-hidden="true" onClick={onClose} />}
      <aside
        id="admin-sidebar"
        className={`fixed inset-y-0 left-0 z-40 w-64 shrink-0 bg-gray-900 text-gray-300 flex flex-col transition-transform lg:static lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full invisible lg:visible'
        }`}
      >
        <div className="h-16 flex items-center justify-between px-6 text-lg font-bold text-white border-b border-gray-800">
          AlakhService Admin
          <button
            ref={closeRef}
            type="button"
            aria-label="Close menu"
            onClick={onClose}
            className="lg:hidden p-1 -mr-2 rounded text-gray-300 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>
        <nav aria-label="Main" className="flex-1 overflow-y-auto py-4 space-y-6">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title}>
              <p className="px-6 mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">{section.title}</p>
              {section.items.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-6 py-2 text-sm border-l-2 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-indigo-400 ${
                      isActive ? 'bg-gray-800 text-white border-indigo-400' : 'border-transparent hover:bg-gray-800 hover:text-white'
                    }`
                  }
                >
                  <Icon size={18} aria-hidden="true" />
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}
