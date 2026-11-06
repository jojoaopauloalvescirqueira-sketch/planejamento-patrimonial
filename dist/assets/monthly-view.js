/* Compatibility adapter: all amounts now come from the shared engine read policy. */
(function (root) {
  'use strict';
  const planning = root.JPWPlanning;
  function balances(plan, today, options = {}) {
    const rows = options.rows || planning.engine.timeline(plan, {...options, month: today, balancePolicy: 'confirmed-projection'});
    const result = {};
    for (const row of rows) {
      const filled = planning.monthlyInputs.status(plan, row.month);
      result[row.month] = {projectionStatus:row.projectionStatus,blockingMonth:row.blockingMonth,
        status:row.projectionStatus==='WAITING_CLOSURE'?'WAITING_CLOSURE':row.finalized?'CONFIRMED':row.month>today?'PROJECTED':row.closeUsd===null?'NOT_COMPUTABLE':filled.result&&filled.contribution&&filled.withdrawal?'RECORDED':'PARTIAL',
        openUsd:row.openUsd,closeUsd:row.closeUsd,closeBrl:row.closeBrl};
    }
    return result;
  }
  planning.monthlyView = Object.freeze({balances});
})(window);
