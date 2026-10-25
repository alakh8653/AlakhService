import { defaultLegalLinks } from '../services/legal';

/** Links to the public legal pages, at the bottom of every screen. */
export default function LegalFooter({ className = '' }: { className?: string }) {
  const links = defaultLegalLinks();
  const items = [
    { href: links.termsUrl, label: 'Terms' },
    { href: links.privacyUrl, label: 'Privacy' },
    { href: links.refundUrl, label: 'Refunds' },
    { href: links.grievanceUrl, label: 'Grievance officer' },
    { href: links.deleteAccountUrl, label: 'Delete account' },
  ];
  return (
    <footer className={`text-xs text-gray-500 ${className}`}>
      <nav aria-label="Legal">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 justify-center">
          {items.map((i) => (
            <li key={i.label}>
              <a href={i.href} target="_blank" rel="noopener noreferrer" className="hover:text-indigo-600 hover:underline">
                {i.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </footer>
  );
}
