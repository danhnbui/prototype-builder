function renderScreenDetail() {
  // Shows the request that was tapped. Approve stays visible and disabled for a role that can't:
  // a reviewer should see the step exists, a requester should see they cannot take it.
  var id = pbCtx() || 'no request';
  return '<div data-testid="detail" style="padding:var(--space-6)">'
    + pbUse('heading', { level: 1, text: 'Request detail' })
    + '<div data-testid="subject">' + pbEscape(id) + '</div>'
    + '<div data-testid="can-approve">' + (pbCan('request', 'approve') ? 'can approve' : 'cannot approve') + '</div>'
    + pbUse('demo-action', { label: 'Approve', nav: 'done', can: 'request:approve', canMode: 'disable', testId: 'approve' })
    + pbUse('demo-action', { label: 'Back', back: 'requests', testId: 'back' })
    + '</div>';
}
