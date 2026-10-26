/* Interface text and bilingual rendering shared by every page. Rules: docs/language.md. */
const UI_TEXT = {
  switch_language: { en:'Switch to Chinese', zh:'切换到英文' },
  loading_data: { en:'Loading data…', zh:'正在获取数据…' },
  strategy: { en:'Strategy', zh:'策略' },
  market: { en:'Market', zh:'市场指标' },
  symbols: { en:'Symbols', zh:'标的' },
  rule_catalog: { en:'Rule catalog', zh:'规则目录' },
  select_symbol: { en:'Select a symbol on the left to see its strategy tree', zh:'选择左侧的标的查看策略树' },
  switch_theme: { en:'Switch light or dark mode', zh:'切换浅色或深色模式' },
  pass: { en:'Pass', zh:'通过' }, fail: { en:'Fail', zh:'未通过' }, veto: { en:'Veto', zh:'否决' },
  unknown: { en:'Unknown', zh:'未知' }, not_applicable: { en:'N/A', zh:'不适用' },
  unavailable: { en:'Unavailable', zh:'获取失败' },
  symbol_summary: { en:'{symbol}, {status}, score {score}', zh:'{symbol}，{status}，分数 {score}' },
  insufficient_data: { en:'Insufficient data', zh:'数据不足' },
  disconnected: { en:'Disconnected, retrying', zh:'连接断开，正在重试' },
  market_closed: { en:'Market closed · Last update {time}', zh:'休市 · 最后更新 {time}' },
  data_stale: { en:'Data is stale · Last update {time}', zh:'数据已过期 · 最后更新 {time}' },
  market_open: { en:'Market open · Updated {age}', zh:'开盘中 · 更新于 {age}' },
  generated_at: { en:'Data generated at {time}', zh:'数据生成于 {time}' },
  just_now: { en:'just now', zh:'刚刚' },
  minutes_ago: { en:'{count} min ago', zh:'{count} 分钟前' },
  hours_ago: { en:'{count} h ago', zh:'{count} 小时前' },
  yes: { en:'Yes', zh:'是' }, no: { en:'No', zh:'否' },
  back_to_list: { en:'↑ List', zh:'↑ 列表' },
  verdict: { en:'Verdict', zh:'结论' }, score: { en:'Score', zh:'分数' },
  missing_weight: { en:'Missing-data weight {percent}% (unknown rules are left out of the score)', zh:'数据缺失权重 {percent}%（未知规则不计入分数）' },
  about_strategy: { en:'About {name}', zh:'{name} 策略说明' },
  close: { en:'Close', zh:'关闭说明' },
  source: { en:'Source: {source}', zh:'来源：{source}' },
  see_all_rules: { en:'See all rules and how IDs work →', zh:'查看全部规则和编号说明 →' },
  best_window: { en:'Expiration {label} days (best) · Gate score {score}', zh:'到期窗口 {label} 天（最佳） · 本层分数 {score}' },
  alternative_window: { en:'Alternative expiration {label} days · Gate score {score}', zh:'备选到期窗口 {label} 天 · 本层分数 {score}' },
  rule_details: { en:'Show all fields of {id}', zh:'查看 {id} 的全部字段' },
  open_rule: { en:'Open {id} in the rule catalog', zh:'在规则目录中查看 {id}' },
  dashboard_title: { en:'StockBoard', zh:'StockBoard' },
  rules_title: { en:'Rule catalog · StockBoard', zh:'规则目录 · StockBoard' },
  back_to_dashboard: { en:'← Back to dashboard', zh:'← 返回看板' },
  rule_summary: { en:'{total} rules · {built} built · {backtest} can be backtested · {used} used by strategies', zh:'共 {total} 条规则 · 已接入 {built} 条 · 可回测 {backtest} 条 · 被策略使用 {used} 条' },
  backtest_rules: { en:'Can be backtested', zh:'可以回测的规则' },
  backtest_explanation: { en:'Backtest: a rule can be backtested when free historical data can rebuild what it would have said on a past date, using only what was known then. How far back differs by rule; rules that need your own answer or your account cannot be backtested.',
    zh:'回测：如果免费的历史数据能还原这条规则在过去某一天、只用当时已知信息会给出的结果，这条规则就可以回测。能追溯多久因规则而异；需要你本人回答或你的账户数据的规则不能回测。' },
  id_explanation: { en:'How IDs work: R- plus a three-letter category and two digits, such as R-TRD-05. Categories run from macro down to detail. Inside a category the numbers run 01, 02, 03 ... in the order shown, grouped into topics. One ID means the same rule in every strategy. A rule only says pass, fail or unknown; each strategy gives it its own weight.',
    zh:'编号规则：R- 加三个字母的分类和两位数字，如 R-TRD-05。分类从宏观排到细节。分类内的编号按显示顺序 01、02、03……依次排下去，并按主题分组。同一个编号在所有策略里是同一条规则。一条规则只回答通过、不通过或未知；权重由每个策略自己决定。' },
  gap_explanation: { en:'A measure with several lines, such as the VIX, is split into one rule per line (VIX at least 12, at least 15, below 25 ...). A strategy lists the lines it wants, each with its own weight, so crossing one more line adds weight. The other lines of a measure sit right under its main rule, indented, and share the indicator text.',
    zh:'有多条分界线的指标（如 VIX）被拆成一线一条规则（VIX 不低于 12、不低于 15、低于 25 ……）。策略自己挑要用的线，并给每条线单独的权重，所以越过的线越多，得到的权重越多。同一指标的其他线紧挨在主规则下面，缩进显示，共用同一份指标说明。' },
  status_label: { en:'Status', zh:'状态' },
  show: { en:'Show', zh:'显示' },
  indicator_lines: { en:'Lines of {id}', zh:'{id} 的各档' },
  all_rules: { en:'All rules', zh:'全部规则' },
  used_rules: { en:'Used by a strategy', zh:'已被策略使用的规则' },
  built_rules: { en:'Built (the dashboard computes them)', zh:'已接入（看板在计算）的规则' },
  not_used: { en:'Not used', zh:'未被使用' },
  loading_rules: { en:'Loading rules…', zh:'正在读取规则…' },
  rules_failed: { en:'Could not load rules. Check that the server is running.', zh:'读取规则失败，请确认服务正在运行。' },
  built: { en:'Built', zh:'已接入' },
  built_explanation: { en:'the dashboard already computes it', zh:'看板已经在计算' },
  todo: { en:'To do', zh:'待实现' },
  todo_explanation: { en:'the data is free and easy to get, the code is not written yet', zh:'数据免费、容易取得，代码还没写' },
  no_data: { en:'No data', zh:'暂无数据' },
  no_data_explanation: { en:'no stable free data, or a manual rule; it shows unknown and is left out of the score', zh:'没有稳定的免费数据，或是手填规则；显示未知，不计入分数' },
  api_fetch: { en:'auto fetch', zh:'自动抓取' },
  scrape: { en:'scrape', zh:'复杂抓取' },
  computed: { en:'computed', zh:'计算获得' },
  ai_search: { en:'AI search', zh:'AI 采集' },
  manual: { en:'manual', zh:'手填' },
};
const LANGUAGE_STORAGE_KEY = 'stockboard-language';
let activeLanguage = 'en', hasStoredLanguageChoice = false;

const languageEscape = text => String(text ?? '').replace(/[&<>"]/g, character => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' })[character]);
const languageFill = (localizedText, values = {}) => Object.fromEntries(['en', 'zh'].map(code =>
  [code, localizedText[code].replace(/\{(\w+)\}/g, (match, name) => values[name] ?? match)]));
const languageLocalize = (key, values) => languageFill(UI_TEXT[key], values);
const languageText = (key, values) => languageLocalize(key, values)[activeLanguage];
const languageGetActive = () => activeLanguage;

function languageInitialize(defaultLanguage) {
  let storedChoice = null;
  try { storedChoice = localStorage.getItem(LANGUAGE_STORAGE_KEY); } catch (error) { /* storage blocked: use the default */ }
  hasStoredLanguageChoice = storedChoice === 'en' || storedChoice === 'zh';
  activeLanguage = hasStoredLanguageChoice ? storedChoice : (defaultLanguage === 'zh' ? 'zh' : 'en');
  languageApplyDocument();
}
function languageApplyServerDefault(defaultLanguage, onChange) {
  if (!hasStoredLanguageChoice && (defaultLanguage === 'zh' ? 'zh' : 'en') !== activeLanguage) { activeLanguage = defaultLanguage; languageApplyDocument(); onChange(); }
}
function languageApply(languageCode, onChange) {
  activeLanguage = languageCode; hasStoredLanguageChoice = true;
  try { localStorage.setItem(LANGUAGE_STORAGE_KEY, languageCode); } catch (error) { /* storage blocked: lasts this visit only */ }
  languageApplyDocument();
  onChange();
}
function languageApplyDocument() {
  document.documentElement.lang = activeLanguage === 'zh' ? 'zh-Hans' : 'en';
  if (document.body.dataset.titleKey) document.title = languageText(document.body.dataset.titleKey);
  const languageButton = document.getElementById('language-button');
  if (languageButton) { languageButton.setAttribute('aria-label', languageText('switch_language')); languageButton.title = languageText('switch_language'); }
}
/* In Chinese mode the English goes in <small lang="en">, always on its own line directly under the Chinese. */
/* A rule_name or indicator_name, escaped, with a place to break after each underscore so a long name wraps instead of overflowing. */
function languageRenderName(name) {
  return languageEscape(name).replace(/_/g, '_<wbr>');
}
function languageRenderText(localizedText) {
  const primary = languageEscape(localizedText[activeLanguage]);
  if (activeLanguage !== 'zh') return primary;
  return `${primary}<small lang="en">${languageEscape(localizedText.en)}</small>`;
}
function languageRenderParagraphs(localizedText) {
  const split = text => text.split(/\n\s*\n/).map(paragraph => paragraph.trim()).filter(Boolean);
  const englishList = split(localizedText.en);
  if (activeLanguage !== 'zh') return englishList.map(paragraph => `<p>${languageEscape(paragraph)}</p>`).join('');
  return split(localizedText.zh).map((paragraph, index) => `<p>${languageEscape(paragraph)}</p>`
    + (englishList[index] ? `<small lang="en">${languageEscape(englishList[index])}</small>` : '')).join('');
}
function languageBindSwitch(onChange) {
  document.getElementById('language-button').onclick = () => languageApply(activeLanguage === 'zh' ? 'en' : 'zh', onChange);
  languageApplyDocument();
}
