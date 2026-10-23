// Account deletion with a one-time code: send-otp (purpose delete_account), then delete-account/otp.
'use strict';

document.addEventListener('DOMContentLoaded', () => {
  const { post, message, normaliseIdentifier, setStatus } = window.alakh;
  const requestForm = document.getElementById('request-form');
  const confirmForm = document.getElementById('confirm-form');
  const status = document.getElementById('status');
  let identifier = '';

  requestForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    identifier = normaliseIdentifier(document.getElementById('identifier').value);
    if (!identifier) return setStatus(status, 'Enter the email or mobile number on your account.', 'error');
    const button = requestForm.querySelector('button');
    button.disabled = true;
    setStatus(status, 'Sending…');
    const result = await post('/auth/send-otp', { phone_or_email: identifier, purpose: 'delete_account' });
    button.disabled = false;
    if (!result.ok) return setStatus(status, message(result, 'Could not send a code. Please try again.'), 'error');
    // The same answer whether or not an account exists, so this page cannot be used to probe accounts.
    document.getElementById('sent-to').textContent =
      'If an account uses ' + identifier + ', we have sent it a code. It expires in a few minutes.';
    requestForm.hidden = true;
    confirmForm.hidden = false;
    setStatus(status, '');
    document.getElementById('code').focus();
  });

  confirmForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const code = document.getElementById('code').value.trim();
    if (!code) return setStatus(status, 'Enter the code we sent you.', 'error');
    if (!document.getElementById('sure').checked) {
      return setStatus(status, 'Please tick the box to confirm.', 'error');
    }
    const button = confirmForm.querySelector('button[type="submit"]');
    button.disabled = true;
    setStatus(status, 'Deleting…');
    const result = await post('/auth/delete-account/otp', { phone_or_email: identifier, code });
    button.disabled = false;
    if (result.ok) {
      confirmForm.hidden = true;
      return setStatus(status, 'Your account has been deleted. Thank you for using AlakhService.', 'ok');
    }
    const fallback = result.status === 401 ? 'That code is wrong or has expired.' : 'Could not delete the account right now. Please try again.';
    setStatus(status, result.status === 401 ? fallback : message(result, fallback), 'error');
  });

  document.getElementById('start-over').addEventListener('click', () => {
    confirmForm.hidden = true;
    requestForm.hidden = false;
    setStatus(status, '');
  });
});
