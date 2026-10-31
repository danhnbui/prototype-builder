function renderScreenRequests() {
  // The list follows the data seed. Each row carries its subject with data-ctx, and the two
  // actions below are gated two ways: by capability (data-can) and by role (data-roles).
  var open = pbSeed() === 'two-open' ? ['R-1', 'R-2'] : [];
  var rows = open.map(function (id) {
    return pbUse('demo-action', { label: 'Request ' + id, nav: 'detail', ctx: id, testId: 'row-' + id });
  }).join('');
  return '<div data-testid="requests" style="padding:var(--space-6)">'
    + pbUse('heading', { level: 1, text: 'Requests' })
    + (rows || '<div data-testid="empty">No requests yet</div>')
    + pbUse('demo-action', { label: 'New request', can: 'request:request', testId: 'new-request' })
    + pbUse('demo-action', { label: 'Monthly report', can: 'report', roles: 'reviewer admin', testId: 'report' })
    + pbUse('demo-action', { label: 'Back', back: 'welcome', testId: 'back' })
    + '</div>';
}
