function renderScreenDone() {
  // The end of a flow. data-nav-reset empties the back stack as this screen is left, because
  // going back into a finished approval would be a lie.
  return '<div data-nav-reset data-testid="done" style="padding:var(--space-6)">'
    + pbUse('heading', { level: 1, text: 'Approved' })
    + pbUse('demo-action', { label: 'Back to requests', nav: 'requests', testId: 'to-requests' })
    + '</div>';
}
