function renderCmpDemoAction(props) {
  props = props || {};
  // Declarative runtime attributes, passed through from the composing screen.
  var a = '';
  if (props.nav)     a += ' data-nav="' + pbEscape(props.nav) + '"';
  if (props.ctx)     a += ' data-ctx="' + pbEscape(props.ctx) + '"';
  if (props.can)     a += ' data-can="' + pbEscape(props.can) + '"';
  if (props.canMode) a += ' data-can-mode="' + pbEscape(props.canMode) + '"';
  if (props.back)    a += ' data-back="' + pbEscape(props.back) + '"';
  if (props.roles)   a += ' data-roles="' + pbEscape(props.roles) + '"';
  if (props.testId)  a += ' data-testid="' + pbEscape(props.testId) + '"';
  return '<button type="button" class="demo-action"' + a + '>' + pbEscape(props.label || '') + '</button>';
}
