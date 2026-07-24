function renderCmpLoginCard(props) {
  // Organism: composes lower-level atoms (heading + paragraph) — never inlines its own text.
  return '<div class="card" style="width:var(--w-card);max-width:100%;box-sizing:border-box;padding:var(--space-6);background:var(--surface);border:var(--border-width) solid var(--border);border-radius:var(--radius-medium);box-shadow:var(--shadow-md);display:flex;flex-direction:column;gap:var(--space-3)">'
    + pbUse('heading', { level: 2, text: 'Sign in', className: 'card__title' })
    + pbUse('paragraph', { text: 'Welcome back — enter your details to continue.', className: 'card__sub' })
    + '</div>';
}
