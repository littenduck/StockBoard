/* Hover card for the dashboard: a rule's id, name and description. The full record is on the rule catalog page. */
const RULE_CARD_SHOW_DELAY_MS = 1000;
const ruleCard = document.createElement('div');
ruleCard.id = 'rule-card';
ruleCard.className = 'box';
ruleCard.setAttribute('popover', 'manual');
ruleCard.setAttribute('role', 'tooltip');
document.body.appendChild(ruleCard);
const ruleById = {};
let ruleCardShowTimer = null;

async function ruleCardLoadRules() {
  const data = await (await fetch('/api/v1/rules')).json();
  data.group_list.forEach(group => group.rule_list.forEach(rule => { ruleById[rule.rule_id] = rule; }));
}

function ruleCardHide() {
  clearTimeout(ruleCardShowTimer);
  if (ruleCard.matches(':popover-open')) ruleCard.hidePopover();
}

function ruleCardShow(trigger) {
  const rule = ruleById[trigger.dataset.rule];
  if (!rule) return;
  ruleCard.innerHTML = `<small>${languageEscape(rule.rule_id)}</small><h3>${languageRenderText(rule.name)}</h3><p>${languageRenderText(rule.description)}</p>`;
  if (!ruleCard.matches(':popover-open')) ruleCard.showPopover();
  const anchor = trigger.getBoundingClientRect(), card = ruleCard.getBoundingClientRect();
  const wantedTop = anchor.bottom + card.height + 8 <= window.innerHeight ? anchor.bottom + 4 : anchor.top - card.height - 4;
  ruleCard.style.top = `${Math.max(8, Math.min(wantedTop, window.innerHeight - card.height - 8))}px`;
  ruleCard.style.left = `${Math.max(8, Math.min(anchor.left, window.innerWidth - card.width - 8))}px`;
}

/* Hover waits a moment before the card opens and closes it the instant the pointer leaves; keyboard focus opens it at once. */
function ruleCardBind(root) {
  const findTrigger = event => event.target.closest && event.target.closest('[data-rule]');
  root.addEventListener('mouseover', event => {
    const trigger = findTrigger(event);
    if (!trigger || trigger.contains(event.relatedTarget)) return;
    ruleCardHide();
    ruleCardShowTimer = setTimeout(() => ruleCardShow(trigger), RULE_CARD_SHOW_DELAY_MS);
  });
  root.addEventListener('mouseout', event => { const trigger = findTrigger(event); if (trigger && !trigger.contains(event.relatedTarget)) ruleCardHide(); });
  root.addEventListener('focusin', event => { const trigger = findTrigger(event); if (trigger) ruleCardShow(trigger); });
  root.addEventListener('focusout', event => { if (findTrigger(event)) ruleCardHide(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') ruleCardHide(); });
  window.addEventListener('scroll', ruleCardHide, true);
}
