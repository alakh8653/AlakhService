import { Link, useLocation } from 'react-router-dom';
import { AlertTriangle, ShieldCheck } from 'lucide-react';
import { verificationOf } from '../services/shopService';
import type { Shop } from '../types';

/** Shown on every page until the shop is approved: why customers cannot find it yet, and what to do. */
export default function OnboardingBanner({ shop }: { shop: Shop }) {
  const { pathname } = useLocation();
  const status = verificationOf(shop);
  if (status === 'APPROVED') return null;
  const onPage = pathname === '/onboarding';

  if (status === 'REJECTED') {
    return (
      <div role="status" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 flex flex-col sm:flex-row sm:items-center gap-3">
        <AlertTriangle size={20} className="shrink-0" aria-hidden />
        <div className="flex-1">
          <p className="font-semibold">Verification was not approved. Customers cannot see your shop.</p>
          {shop.rejectionReason && <p>Reason: {shop.rejectionReason}</p>}
        </div>
        {!onPage && (
          <Link to="/onboarding" className="self-start sm:self-auto whitespace-nowrap rounded-lg bg-red-600 px-3 py-2 font-medium text-white hover:bg-red-700">
            Fix and resubmit
          </Link>
        )}
      </div>
    );
  }

  const submitted = !!shop.submittedAt;
  return (
    <div role="status" className="mb-4 rounded-xl border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-900 flex flex-col sm:flex-row sm:items-center gap-3">
      <ShieldCheck size={20} className="shrink-0" aria-hidden />
      <p className="flex-1">
        {submitted
          ? 'Your shop is being reviewed. Customers can find and book it once it is approved.'
          : 'Your shop is not visible to customers yet. Add your business details and documents, then submit them for review.'}
      </p>
      {!onPage && (
        <Link to="/onboarding" className="self-start sm:self-auto whitespace-nowrap rounded-lg bg-yellow-700 px-3 py-2 font-medium text-white hover:bg-yellow-800">
          {submitted ? 'View verification' : 'Complete verification'}
        </Link>
      )}
    </div>
  );
}
