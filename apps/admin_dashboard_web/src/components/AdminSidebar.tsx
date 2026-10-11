import { NavLink } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  FileClock,
  Gauge,
  KeyRound,
  Scale,
  ShieldCheck,
  Wallet,
  Users,
  type LucideIcon,
} from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Operations',
    items: [
      { to: '/users', label: 'Users', icon: Users },
      { to: '/audit', label: 'Audit Logs', icon: FileClock },
      { to: '/disputes', label: 'Disputes', icon: Scale },
    ],
  },
  {
    title: 'Finance',
    items: [
      { to: '/finance/settlements', label: 'Settlements', icon: Wallet },
      { to: '/finance/revenue', label: 'Revenue Report', icon: BarChart3 },
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

export default function AdminSidebar() {
  return (
    <aside className="w-64 shrink-0 bg-gray-900 text-gray-300 flex flex-col">
      <div className="h-16 flex items-center px-6 text-lg font-bold text-white border-b border-gray-800">
        AlakhService Admin
      </div>
      <nav className="flex-1 overflow-y-auto py-4 space-y-6">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title}>
            <p className="px-6 mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">{section.title}</p>
            {section.items.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-6 py-2 text-sm ${isActive ? 'bg-gray-800 text-white' : 'hover:bg-gray-800 hover:text-white'}`
                }
              >
                <Icon size={18} />
                {label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
