function renderScreenWelcome() {
  // The start of the whole-flow demo: says who is signed in, from the persona or the role.
  var who = pbPersona();
  var name = who ? who.name : (pbRole() || 'nobody');
  return '<div data-testid="welcome" style="padding:var(--space-6)">'
    + pbUse('heading', { level: 1, text: 'Request desk' })
    + '<div data-testid="who">' + pbEscape('Signed in as ' + name) + '</div>'
    + pbUse('demo-action', { label: 'Open requests', nav: 'requests', testId: 'open-requests' })
    + '</div>';
}
