var err = props.state === 'error';
return '<div class="field" style="display:flex;flex-direction:column;gap:var(--space-1);width:100%;max-width:var(--w-card)">'
  + '<label class="field__label" style="font-family:var(--font-body);font-size:var(--text-xs);font-weight:600;color:var(--text-active-secondary)">' + (props.label || 'Email') + '</label>'
  + '<input class="field__input" type="text" data-required placeholder="' + (props.placeholder || '') + '" style="width:100%;height:var(--size-field);padding:0 var(--space-3);border:var(--border-width) solid ' + (err ? 'var(--danger)' : 'var(--border-strong)') + ';border-radius:var(--radius-small);font-family:var(--font-body);font-size:var(--text-sm);box-sizing:border-box" />'
  + (err ? '<span class="field__help" style="font-family:var(--font-body);font-size:var(--text-xs);color:var(--danger)">Enter a valid email address.</span>' : '')
  + '</div>';
