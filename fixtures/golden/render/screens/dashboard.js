function renderScreenDashboard(props) {
  // Page: pure composition — a layout shell + atoms via pbUse(). No inlined controls.
  return '<div style="min-height:100%;padding:var(--space-8);background:var(--bg-soft);display:flex;flex-direction:column;align-items:flex-start;gap:var(--space-2)">'
    + pbUse('heading', { level: 1, text: 'Welcome back' })
    + pbUse('paragraph', { text: 'You are signed in.', tone: 'muted' })
    + pbUse('button', { label: 'Admin settings', dataRoles: 'admin', dataNav: 'account' })
    + '</div>';
}
