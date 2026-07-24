function renderScreenLogin(props) {
  // Page: pure composition — a layout shell + atoms via pbUse(). No inlined controls.
  return '<div style="min-height:100%;display:flex;align-items:center;justify-content:center;background:var(--bg-soft);padding:var(--space-8)">'
    + '<div class="card" style="width:var(--w-card);padding:var(--space-6);background:var(--surface);border:var(--border-width) solid var(--border);border-radius:var(--radius-medium);display:flex;flex-direction:column;gap:var(--space-3)">'
    + pbUse('heading', { level: 1, text: 'Sign in' })
    + pbUse('text-input', { label: 'Email', placeholder: 'you@example.com', type: 'text', dataHandoffEl: 'email', dataRequired: true, dataValidate: 'email' })
    + pbUse('text-input', { label: 'Password', placeholder: 'Password', type: 'password', dataHandoffEl: 'password', dataRequired: true, dataMinlength: 8 })
    + pbUse('button', { label: 'Sign in', full: true, dataAction: 'submit', dataGo: 'dashboard', dataHandoffEl: 'submit' })
    + pbUse('button', { label: 'Create an account', variant: 'link', dataNav: 'account' })
    + '</div></div>';
}
