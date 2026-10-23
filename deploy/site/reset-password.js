// Sets a new password with the token from the reset email (?token=...).
'use strict';

document.addEventListener('DOMContentLoaded', () => {
  const { post, message, setStatus } = window.alakh;
  const form = document.getElementById('reset-form');
  const status = document.getElementById('status');
  const token = new URLSearchParams(window.location.search).get('token') || '';
  // Keep the token out of the address bar (and so out of history and screenshots).
  if (token && window.history.replaceState) window.history.replaceState(null, '', window.location.pathname);

  if (!token) {
    form.hidden = true;
    setStatus(status, 'This link is incomplete. Ask for a new reset email from the app or the shop dashboard.', 'error');
    return;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const password = document.getElementById('password').value;
    if (password !== document.getElementById('confirm').value) {
      return setStatus(status, 'The two passwords do not match.', 'error');
    }
    const button = form.querySelector('button');
    button.disabled = true;
    setStatus(status, 'Saving…');
    const result = await post('/auth/reset-password', { token, new_password: password });
    button.disabled = false;
    if (result.ok) {
      form.hidden = true;
      document.getElementById('done').hidden = false;
      return setStatus(status, 'Your password has been changed.', 'ok');
    }
    const expired = result.status === 401 || result.status === 400;
    setStatus(
      status,
      expired ? 'This link has expired or was already used. Ask for a new reset email.' : message(result, 'Could not change the password. Please try again.'),
      'error',
    );
  });
});
