function renderCmpButton(props) {
  props = props || {};
  var variant = props.variant === 'link' ? 'link' : 'primary';
  var dis = props.state === 'disabled';
  // Declarative runtime attributes, passed through from the composing screen/organism.
  var a = '';
  if (props.dataAction)     a += ' data-action="' + pbEscape(props.dataAction) + '"';
  if (props.dataGo)         a += ' data-go="' + pbEscape(props.dataGo) + '"';
  if (props.dataNav)        a += ' data-nav="' + pbEscape(props.dataNav) + '"';
  if (props.dataToast)      a += ' data-toast="' + pbEscape(props.dataToast) + '"';
  if (props.dataRedirect)   a += ' data-redirect="' + pbEscape(props.dataRedirect) + '"';
  if (props.dataRedirectMs) a += ' data-redirect-ms="' + pbEscape(props.dataRedirectMs) + '"';
  if (props.dataHandoffEl)  a += ' data-handoff-el="' + pbEscape(props.dataHandoffEl) + '"';
  if (props.dataRoles)      a += ' data-roles="' + pbEscape(props.dataRoles) + '"';
  if (dis)                  a += ' disabled';
  var style = (variant === 'link')
    ? 'display:inline-block;margin-top:var(--space-4);padding:0;background:none;border:0;color:var(--brand);font-family:var(--font-body);font-size:var(--text-sm);cursor:pointer'
    : 'height:var(--size-control);padding:0 var(--space-5);border:0;border-radius:var(--radius-small);background:var(--brand);color:var(--on-brand);font-family:var(--font-body);font-size:var(--text-sm);font-weight:600;cursor:pointer'
      + (props.full ? ';width:100%' : '') + (dis ? ';opacity:0.5' : '');
  return '<button class="btn btn--' + variant + '"' + a + ' style="' + style + '">' + pbEscape(props.label || 'Continue') + '</button>';
}
