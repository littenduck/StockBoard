/* The financial panel: the company numbers the rules use, grouped like the rules (IND, QUA, MGT, VAL, ACC), with the unit and the source. */
const FUNDAMENTAL_GROUP_TEXT = {
  IND: { en:'Industry', zh:'行业' }, QUA: { en:'Company quality', zh:'公司质量' }, MGT: { en:'Management and governance', zh:'管理层与治理' },
  VAL: { en:'Valuation', zh:'估值' }, ACC: { en:'Accounting quality', zh:'会计质量' } };

function formatFundamentalValue(value, unit) {
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  // Amounts in dollars are shown in billions; a per-share or ratio value keeps its own digits, so 8.72 is not shown as 0.00 bn.
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(2)} bn`;
  const text = Number(value).toFixed(Math.abs(value) < 10 ? 2 : 1);
  return unit ? `${text} ${unit}` : text;
}

async function loadFundamentalsPanel(symbol) {
  const panel = document.getElementById('fundamental-panel');
  if (!panel) return;
  try {
    const response = await fetch(`/api/v1/fundamentals/${encodeURIComponent(symbol)}`);
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    if (panel.dataset.symbol !== symbol) return; // the user has moved to another stock
    const groups = Object.keys(FUNDAMENTAL_GROUP_TEXT).map(group => {
      const rows = data.value_list.filter(item => item.group_id === group);
      if (!rows.length) return '';
      return `<h3>${languageRenderText(FUNDAMENTAL_GROUP_TEXT[group])}</h3>` + rows.map(item => `<div class="row">
        <span>${languageRenderName(item.indicator_name)}</span><span>${escapeText(formatFundamentalValue(item.value, item.unit))}</span>
        <small>${escapeText(item.source)}</small></div>`).join('');
    }).join('');
    panel.innerHTML = `<h2>${languageRenderText({ en:'Fundamental numbers', zh:'基本面数字' })}</h2>
      ${groups || `<small>${languageRenderText({ en:'No numbers yet. They appear after the next refresh.', zh:'暂时没有数字，下次刷新后显示。' })}</small>`}`;
  } catch (error) {
    if (panel.dataset.symbol === symbol) panel.innerHTML = `<small>${languageRenderText({ en:'Could not load the numbers.', zh:'无法加载数字。' })}</small>`;
  }
}
