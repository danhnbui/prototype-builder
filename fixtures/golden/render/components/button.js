function renderCmpButton(props) {
var dis = props.state === 'disabled' ? ' disabled' : ''; return '<button class="btn" data-action="submit"' + dis + ' style="height:var(--size-control);padding:0 var(--space-5);border:0;border-radius:var(--radius-small);background:var(--brand);color:var(--on-brand);font-family:var(--font-body);font-size:var(--text-sm);font-weight:600;cursor:pointer;opacity:' + (dis?'0.5':'1') + '">' + (props.label || 'Continue') + '</button>';
}
