// A shared visit (/v/<token>): its status and when the professional is expected, refreshed every 30 s.
// Only what GET /api/v1/public/shares/<token> returns is shown; it never includes contact details.
'use strict';

(function () {
  const STATUS = {
    PENDING: 'Waiting for the shop to confirm',
    CONFIRMED: 'Confirmed',
    ASSIGNED: 'A professional has been assigned',
    PROVIDER_EN_ROUTE: 'The professional is on the way',
    PICKED_UP: 'The item has been collected',
    IN_PROGRESS: 'The service has started',
    OUT_FOR_DELIVERY: 'The item is on its way back',
    COMPLETED: 'Completed',
    CANCELLED: 'Cancelled',
    REFUNDED: 'Cancelled and refunded',
    DISPUTED: 'Under review by AlakhService',
  };
  const REFRESH_MS = 30000;
  const token = (window.location.pathname.split('/')[2] || '').trim();
  const $ = (id) => document.getElementById(id);
  let timer = null;

  function time(iso) {
    const at = new Date(iso);
    if (Number.isNaN(at.getTime())) return '';
    return at.toLocaleString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
  }

  function minutesFromNow(iso) {
    return Math.round((new Date(iso).getTime() - Date.now()) / 60000);
  }

  function show(visit) {
    $('visit').hidden = false;
    $('status').textContent = STATUS[visit.status] || visit.status;
    const what = [visit.service_name, visit.shop_name && 'by ' + visit.shop_name].filter(Boolean).join(' ');
    $('what').textContent = what;
    $('when').textContent = 'Booked for ' + time(visit.scheduled_at) + '.';
    if (visit.eta) {
      const mins = minutesFromNow(visit.eta);
      const soon = visit.status === 'PROVIDER_EN_ROUTE' && mins > 0 ? ' (about ' + mins + ' min)' : '';
      $('eta').textContent = 'Expected around ' + time(visit.eta) + soon + '.';
    } else {
      $('eta').textContent = '';
    }
    $('who').textContent = visit.provider_first_name ? 'Professional: ' + visit.provider_first_name + '.' : '';
    const loc = visit.provider_location;
    $('where').textContent = loc
      ? 'Last known position: ' + Number(loc.lat).toFixed(4) + ', ' + Number(loc.lng).toFixed(4) +
        (loc.updated_at ? ' (at ' + time(loc.updated_at) + ')' : '') + '.'
      : '';
    $('refreshed').textContent = 'Updated ' + new Date().toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' });
    $('message').textContent = '';
    $('message').className = 'status';
  }

  function fail(text) {
    $('message').textContent = text;
    $('message').className = 'status error';
  }

  async function load() {
    if (!/^[\w-]{10,64}$/.test(token)) {
      $('visit').hidden = true;
      return fail('This link is incomplete. Ask the person who shared it to send it again.');
    }
    let resp;
    try {
      resp = await fetch('/api/v1/public/shares/' + encodeURIComponent(token), { headers: { Accept: 'application/json' } });
    } catch (e) {
      return fail('Could not reach AlakhService. Check your connection; we will try again.');
    }
    if (resp.status === 404) {
      window.clearInterval(timer);  // it will not come back
      $('visit').hidden = true;
      return fail('This link has expired or does not exist. Shared visits work until a day after the visit.');
    }
    if (resp.status === 429) return fail('Too many requests. We will try again shortly.');
    if (!resp.ok) return fail('Something went wrong. We will try again shortly.');
    show(await resp.json());
  }

  document.addEventListener('DOMContentLoaded', () => {
    timer = window.setInterval(load, REFRESH_MS);
    load();
  });
})();
