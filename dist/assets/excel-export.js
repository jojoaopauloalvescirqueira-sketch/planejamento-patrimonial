(function (root) {
  'use strict';
  const dialog = document.getElementById('excel-dialog');
  const submit = document.getElementById('excel-download');
  const message = document.getElementById('excel-message');
  const include = document.getElementById('excel-archived');
  const cancel = document.getElementById('excel-cancel');
  let opener = null;
  let busy = false;

  function open(trigger) {
    if (dialog.open) return;
    opener = trigger;
    include.checked = false;
    message.textContent = '';
    dialog.showModal();
    include.focus();
  }
  function historical(document, market, month, archived) {
    const envelope = document.patrimonialPlanning;
    const starts = (envelope?.accounts ?? []).filter(a => a.active || archived).map(a => a.plan?.startMonth);
    if (archived) for (const item of envelope?.archive ?? []) starts.push(item.plan?.startMonth);
    const months = new Set();
    const addMonths = root.JPWPlanning.engine.addMonths;
    for (const start of new Set(starts.filter(Boolean))) {
      for (let i = 0, key = start; i < 120 && key < month; i++, key = addMonths(start,i)) months.add(key);
    }
    const quotes = {};
    for (const key of months) {
      const quote = market?.getHistorical(key);
      if (quote) quotes[key] = quote;
    }
    return quotes;
  }
  dialog.addEventListener('close', () => {
    if (opener?.isConnected) opener.focus({preventScroll:true});
    opener = null;
  });
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  cancel.addEventListener('click', () => dialog.close());
  document.getElementById('excel-open-data').addEventListener('click', event => open(event.currentTarget));
  document.addEventListener('planning-export-excel', event => open(event.detail));
  submit.addEventListener('click', async () => {
    if (busy) return;
    const includeArchived = include.checked;
    busy = true;
    submit.disabled = include.disabled = cancel.disabled = true;
    message.textContent = 'Preparando o arquivo Excel…';
    try {
      // Allow the status to paint, then read and validate a single snapshot.
      await new Promise(resolve => setTimeout(resolve, 30));
      const snapshot = root.PlanningStore.exportDocument();
      const now = new Date();
      const month = now.getFullYear() + '-' + String(now.getMonth()+1).padStart(2,'0');
      const market = root.JPWMarket?.usdBrl;
      const options = {month, at:now.toISOString(), includeArchived, quote:market?.get(),
        historicalQuotes:historical(snapshot,market,month,includeArchived),
        revision:root.PlanningStore.status().revision, version:root.PP_BUILD};
      const tables = root.JPWPlanning.excelModel.prepare(snapshot,options);
      const blob = root.JPWPlanning.excelWriter.workbook(tables,options);
      if (!dialog.open) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'planejamento-patrimonial-' + options.at.slice(0,10) + '.xlsx';
      document.body.append(link);
      try { link.click(); } finally {
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
      message.textContent = 'Arquivo Excel preparado para download.';
    } catch (error) {
      message.textContent = 'Exportação não concluída. ' + (error.message ?? '');
    } finally {
      busy = false;
      submit.disabled = include.disabled = cancel.disabled = false;
    }
  });
})(window);
