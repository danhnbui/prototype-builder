function renderCmpTextInput(props) {
  props = props || {};
  var err = props.state === 'error';
  // Declarative validation attributes, passed through from the composing screen.
  var a = ' type="' + pbEscape(props.type || 'text') + '"';
  if (props.dataHandoffEl) a += ' data-handoff-el="' + pbEscape(props.dataHandoffEl) + '"';
  if (props.dataRequired)  a += ' data-required';
  if (props.dataValidate)  a += ' data-validate="' + pbEscape(props.dataValidate) + '"';
  if (props.dataMinlength) a += ' data-minlength="' + pbEscape(props.dataMinlength) + '"';
  return '<div class="field" style="display:flex;flex-direction:column;gap:var(--space-1);width:100%">'
    + '<label class="field__label" style="font-family:var(--font-body);font-size:var(--text-xs);font-weight:600;color:var(--text-active-secondary)">' + pbEscape(props.label || 'Email') + '</label>'
    + '<input class="field__input"' + a + ' placeholder="' + pbEscape(props.placeholder || '') + '" style="width:100%;height:var(--size-field);padding:0 var(--space-3);border:var(--border-width) solid ' + (err ? 'var(--danger)' : 'var(--border-strong)') + ';border-radius:var(--radius-small);font-family:var(--font-body);font-size:var(--text-sm);box-sizing:border-box" />'
    + (err ? '<span class="field__help" style="font-family:var(--font-body);font-size:var(--text-xs);color:var(--danger)">Enter a valid email address.</span>' : '')
    + '</div>';
}
