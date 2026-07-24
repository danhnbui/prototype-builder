function renderCmpParagraph(props) {
  props = props || {};
  var color = props.tone === 'muted' ? 'var(--text-muted)' : 'var(--text-active-secondary)';
  var cls = 'pb-paragraph' + (props.className ? ' ' + props.className : '');
  return '<p class="' + pbEscape(cls) + '" style="font-family:var(--font-body);font-size:var(--text-sm);color:' + color + ';margin:0">'
    + pbEscape(props.text || '') + '</p>';
}
