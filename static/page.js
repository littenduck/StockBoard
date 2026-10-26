/* Shared by the catalog pages (strategies, strategy, rules, indicators): top bar, the entries of a rule and of an indicator, the row named by the URL hash. */
const PAGE_NAV_LIST = [['/', 'nav_dashboard'], ['/strategies', 'nav_strategies'], ['/rules', 'nav_rules'], ['/indicators', 'nav_indicators']];
const PAGE_STATUS_COLOR = { built:'positive', todo:'caution', no_data:'muted' };
const pageText = localizedText => localizedText[languageGetActive()];
const pageSlug = value => encodeURIComponent(value);

let pageCurrent = '/', pageVersion = '';
function pageRenderNav(current) {
  pageCurrent = current;
  document.getElementById('page-nav').innerHTML = PAGE_NAV_LIST.map(([path, key]) =>
    `<small><a href="${path}"${path === current ? ' aria-current="page"' : ''}>${languageEscape(languageText(key))}</a></small>`).join('')
    + (pageVersion ? `<small>${languageEscape(pageVersion)}</small>` : '');
}
fetch('/api/v1/version').then(response => response.json()).then(data => { pageVersion = 'v' + data.version; pageRenderNav(pageCurrent); }).catch(() => { /* no version label */ });

function pageMarkTarget() {
  document.querySelectorAll('.is-target').forEach(row => row.classList.remove('is-target'));
  const row = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (row) row.classList.add('is-target');
  return row;
}
window.addEventListener('hashchange', pageMarkTarget);

/* A line of small facts: only the facts that exist, so there are no empty cells. A fact is [label, value, color class]. */
function pageRenderFacts(factList) {
  const shown = factList.filter(fact => fact && fact[1] != null && fact[1] !== '' && !(Array.isArray(fact[1]) && !fact[1].length));
  return shown.length ? `<small>${shown.map(([label, value, color]) => `${languageEscape(label)}: <span${color ? ` class="${color}"` : ''}>${Array.isArray(value) ? value.map(languageEscape).join(', ') : languageEscape(value)}</span>`).join(' · ')}</small>` : '';
}

function pageRenderDataFacts(item, leadFactList = []) {
  const backtest = item.backtestable === 'yes' ? `yes (${item.history_source} from ${item.history_start})` : item.backtestable;
  return pageRenderFacts([...leadFactList, ['method', item.method && languageText(item.method)], ['quantifiable', item.quantifiable], ['status', languageText(item.status), PAGE_STATUS_COLOR[item.status]],
    ['backtestable', backtest], ['fetch every', item.fetch_every], ['max age', item.max_age]]);
}

function pageRenderUsage(rule) {
  const use = rule.used_by.map(item => `<a href="/strategies/${pageSlug(item.strategy_id)}#rule-${pageSlug(rule.rule_id)}">${languageEscape(pageText(item.display_name))}</a> W${item.weight}${item.veto ? ' · ' + languageEscape(languageText('veto')) : ''}`).join(' · ');
  return use ? `<small>${languageEscape(languageText('used_by_label'))}: ${use}</small>` : '';
}

/* A rule as a card: id, name, pass sentence, what its indicator measures with every line, then the facts. Used by the rules page. */
function pageRenderRuleEntry(rule) {
  const indicatorLink = rule.indicator_id ? `<a href="/indicators#indicator-${rule.indicator_id}">${rule.indicator_id}</a>` : '';
  return `<div class="row" id="rule-${rule.rule_id}" data-tier="${rule.band_of ? 1 : 0}"><small>${rule.rule_id}</small>
    <div><h3>${languageRenderName(rule.rule_name)}</h3><p>${languageRenderText(rule.description)}</p>${rule.band_of ? '' : ruleTextRenderIndicator(rule, true)}
      ${pageRenderDataFacts(rule)}${pageRenderFacts([["older ids", rule.legacy_id]])}${indicatorLink ? `<small>indicator: ${indicatorLink} ${languageRenderName(rule.indicator)}</small>` : ''}
      ${rule.note ? `<small>${languageRenderText(rule.note)}</small>` : ''}${pageRenderUsage(rule)}</div></div>`;
}

/* An indicator as a card: id, long name, what it measures, the facts and the rule lines that test it. */
function pageRenderIndicatorEntry(indicator) {
  const unit = indicator.unit ? ` <small>(${languageEscape(indicator.unit)})</small>` : '';
  const ruleList = indicator.rule_list.map(rule => `<a href="/rules#rule-${rule.rule_id}">${rule.rule_id}</a> ${languageEscape(pageText(rule.line))}`).join(' · ');
  return `<div class="row" id="indicator-${indicator.indicator_id}"><small>${indicator.indicator_id}</small>
    <div><h3>${languageRenderName(indicator.indicator_name)}${unit}</h3><p>${languageRenderText(indicator.description)}</p>
      ${pageRenderDataFacts(indicator, [['scope', indicator.scope]])}
      ${ruleList ? `<small>${languageEscape(languageText('tested_by_label'))}: ${ruleList}</small>` : ''}${indicator.on_market_bar ? `<small>${languageEscape(languageText('on_market_bar'))}</small>` : ''}</div></div>`;
}
