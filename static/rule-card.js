/* Hover card for the dashboard: one rule's full catalog record, in the same field order as config/rules.yaml. */
const RULE_CARD_FIELD_LIST = ['rule_id', 'name', 'description', 'method', 'quantifiable', 'backtestable', 'history_source', 'history_start',
  'status', 'indicator', 'operator', 'value', 'band_of', 'legacy_id', 'note', 'used_by'];
const RULE_CARD_HIDE_DELAY_MS = 150;
const ruleCard = document.createElement('div');
ruleCard.id = 'rule-card';
ruleCard.className = 'box';
ruleCard.setAttribute('popover', 'manual');
ruleCard.setAttribute('role', 'tooltip');
document.body.appendChild(ruleCard);
const ruleById = {};
let ruleCardHideTimer = null;

async function ruleCardLoadRules() {
  const data = await (await fetch('/api/v1/rules')).json();
  data.group_list.forEach(group => group.rule_list.forEach(rule => { ruleById[rule.rule_id] = rule; }));
}

function ruleCardRenderValue(field, rule) {
  const value = rule[field];
  if (field === 'name' || field === 'description') return ['en', 'zh'].map(code =>
    `<p lang="${code === 'en' ? 'en' : 'zh-Hans'}"><small>${code}</small> ${languageEscape(value[code])}</p>`).join('');
  if (field === 'used_by') return value.length ? value.map(use =>
    `<p>${languageEscape(use.strategy_id)} <small>weight</small> ${use.weight}${use.veto ? ' <small>veto</small>' : ''}</p>`).join('') : '<p class="muted">—</p>';
  if (value == null || value === '') return '<p class="muted">—</p>';
  return `<p>${languageEscape(Array.isArray(value) ? value.join(', ') : String(value))}</p>`;
}

function ruleCardShow(trigger) {
  const rule = ruleById[trigger.dataset.rule];
  if (!rule) return;
  clearTimeout(ruleCardHideTimer);
  ruleCard.innerHTML = RULE_CARD_FIELD_LIST.map(field => `<small>${field}</small><div>${ruleCardRenderValue(field, rule)}</div>`).join('');
  ruleCard.showPopover();
  const anchor = trigger.getBoundingClientRect(), card = ruleCard.getBoundingClientRect();
  const fitsBelow = anchor.bottom + card.height + 8 <= window.innerHeight;
  const wantedTop = fitsBelow ? anchor.bottom + 4 : anchor.top - card.height - 4;
  ruleCard.style.top = `${Math.max(8, Math.min(wantedTop, window.innerHeight - card.height - 8))}px`;
  ruleCard.style.left = `${Math.max(8, Math.min(anchor.left, window.innerWidth - card.width - 8))}px`;
}

function ruleCardScheduleHide() {
  clearTimeout(ruleCardHideTimer);
  ruleCardHideTimer = setTimeout(() => ruleCard.hidePopover(), RULE_CARD_HIDE_DELAY_MS);
}

/* Triggers are any element with data-rule inside root; works for rows drawn later. */
function ruleCardBind(root) {
  const findTrigger = event => event.target.closest && event.target.closest('[data-rule]');
  root.addEventListener('mouseover', event => { const trigger = findTrigger(event); if (trigger) ruleCardShow(trigger); });
  root.addEventListener('focusin', event => { const trigger = findTrigger(event); if (trigger) ruleCardShow(trigger); });
  root.addEventListener('mouseout', event => { if (findTrigger(event)) ruleCardScheduleHide(); });
  root.addEventListener('focusout', event => { if (findTrigger(event)) ruleCardScheduleHide(); });
  ruleCard.addEventListener('mouseenter', () => clearTimeout(ruleCardHideTimer));
  ruleCard.addEventListener('mouseleave', ruleCardScheduleHide);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') ruleCard.hidePopover(); });
}
