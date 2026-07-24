function renderCmpHeading(props) {
  props = props || {};
  var lvl = String(props.level) === '2' ? 2 : 1;
  var size = lvl === 1 ? 'var(--text-2xl)' : 'var(--text-lg)';
  var mb = lvl === 1 ? 'var(--space-2)' : '0';
  var cls = 'pb-heading' + (props.className ? ' ' + props.className : '');
  return '<h' + lvl + ' class="' + pbEscape(cls) + '" style="font-family:var(--font-heading);font-size:' + size + ';font-weight:700;margin:0 0 ' + mb + '">'
    + pbEscape(props.text || 'Heading') + '</h' + lvl + '>';
}
