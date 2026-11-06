/* Dedicated format: no JP Wealth document import and no draft authorizations. */
(function (root) {
  'use strict';
  const FORMAT = 'planejamento_patrimonial_backup';
  const exact = (v, keys) => v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).sort().join(',') === keys.slice().sort().join(',');
  const clone = value => structuredClone(value);
  const defaults = () => ({theme: 'light', monthly: {version: 1, highlightPast: true, fromCurrent: false}});
  function preferences(value) {
    if (!exact(value, ['theme', 'monthly']) || !['light', 'dark'].includes(value.theme) ||
        !exact(value.monthly, ['version', 'highlightPast', 'fromCurrent']) || value.monthly.version !== 1 ||
        typeof value.monthly.highlightPast !== 'boolean' || typeof value.monthly.fromCurrent !== 'boolean') throw Error('Preferências incompatíveis.');
    return clone(value);
  }
  function drafts(value, normalize) {
    if (!Array.isArray(value) || value.length > 200) throw Error('Lista de rascunhos incompatível.');
    return value.map(item => {
      if (!item || (!normalize && !exact(item, ['label', 'text'])) || typeof item.label !== 'string' || item.label.length > 500 ||
          typeof item.text !== 'string' || item.text.length > 1024 * 1024) throw Error('Rascunho incompatível.');
      return {label: item.label, text: item.text};
    });
  }
  function inspect(text) {
    if (typeof text !== 'string' || new TextEncoder().encode(text).byteLength > root.PlanningStore.MAX_BYTES) throw Error('Backup excede o limite de32MiB.');
    let value;
    try { value = JSON.parse(text); } catch (_) { throw Error('Arquivo não é um JSON válido.'); }
    if (!exact(value, ['format', 'schemaVersion', 'createdAt', 'document', 'preferences', 'drafts']) || value.format !== FORMAT || ![1,2,3].includes(value.schemaVersion) ||
        typeof value.createdAt !== 'string' || !Number.isFinite(Date.parse(value.createdAt))) throw Error('Este arquivo não é um backup compatível do Planejamento Patrimonial.');
    return {format: FORMAT, schemaVersion: value.schemaVersion, createdAt: value.createdAt,
      document: root.PlanningStore.validateDocument(value.document), preferences: preferences(value.preferences), drafts: drafts(value.drafts, false)};
  }
  root.PlanningBackup = Object.freeze({FORMAT,
    create(options = {}) {
      return inspect(JSON.stringify({format: FORMAT, schemaVersion: 3, createdAt: new Date().toISOString(),
        document: root.PlanningStore.exportDocument(), preferences: options.preferences === undefined ? defaults() : preferences(options.preferences), drafts: drafts(options.drafts === undefined ? [] : options.drafts, true)}));
    },
    inspect,
    restore(inspected, options) {
      let validated;
      try { validated = inspect(JSON.stringify(inspected)); }
      catch (error) { return {status: 'REFUSED', reason: 'INVALID', errors: [error.message]}; }
      const result = root.PlanningStore.restoreDocument(validated.document, options);
      return result.status === 'CONFIRMED' ? {...result, preferences: validated.preferences, drafts: validated.drafts} : result;
    }
  });
})(window);
