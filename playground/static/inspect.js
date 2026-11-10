import { api } from './api.js';

const $ = id => document.getElementById(id);
const pretty = data => JSON.stringify(data, null, 2);

export function initInspect({element, resourceLink, setAccordionState, setBusy, setRequestId, showAssets, getToolState}) {
  const form = $('record-form');
  const submit = $('record-submit');
  const recordIdField = $('record-id');
  let selectedRecordId = recordIdField.value.trim();
  let recordSelectionVersion = 0;

  function updateActions() {
    const {label, available, hint} = getToolState(form.elements['record-mode'].value);
    submit.setAttribute('aria-label', label);
    submit.title = label;
    submit.disabled = form.dataset.busy === 'true' || !available;

    const feedback = $('record-status');
    if (feedback.textContent !== hint) feedback.textContent = hint;
  }

  function selectRecord(recordId) {
    recordIdField.value = recordId;
    recordIdField.dispatchEvent(new Event('input'));
    recordIdField.focus();
  }

  function showMetadata(data, recordId, results) {
    const descriptive = data.content?.descriptiveNonRepeating ?? {};
    const fields = data.content?.freetext ?? {};
    const record = element('article');
    record.className = 'metadata-result';
    const identity = element('div');
    identity.className = 'metadata-identity';
    identity.append(element('h4', data.title || descriptive.title?.content || 'Untitled record'));
    if (descriptive.guid) identity.append(resourceLink(descriptive.guid, 'View Smithsonian record', true));
    const identifier = element('p', descriptive.record_ID || recordId);
    identifier.className = 'metadata-record-id';
    record.append(identity, identifier);

    const facts = element('dl');
    facts.className = 'metadata-facts';
    const objectNames = (fields.objectType ?? []).filter(entry => entry.label?.toLowerCase() === 'object name');
    const catalogNumbers = (fields.identifier ?? []).filter(entry => entry.label?.toLowerCase() === 'catalog number');
    const accessionNumbers = (fields.identifier ?? []).filter(entry => entry.label?.toLowerCase() === 'accession number');
    const entries = [
      ...objectNames.map(entry => ['Object name', entry.content]),
      ...(fields.date ?? []).map(entry => [entry.label || 'Date', entry.content]),
      ...catalogNumbers.map(entry => ['Catalog number', entry.content]),
      ...accessionNumbers.map(entry => ['Accession number', entry.content]),
    ];
    for (const [label, value] of entries) {
      if (!value) continue;
      const fact = element('div');
      fact.append(element('dt', label), element('dd', value));
      facts.append(fact);
    }
    if (facts.childElementCount) record.append(facts);

    const memberships = (fields.setName ?? []).filter(entry => entry.label?.toLowerCase() === 'see more items in');
    const physical = (fields.physicalDescription ?? []).filter(entry => entry.label?.toLowerCase() !== 'measurements');
    const measurements = (fields.physicalDescription ?? []).filter(entry => entry.label?.toLowerCase() === 'measurements');
    for (const [label, items] of [
      ['Collection sets', memberships],
      ['Physical description', physical],
      ['Measurements', measurements],
    ]) {
      const values = items.map(entry => entry.content).filter(Boolean);
      if (!values.length) continue;
      const section = element('section');
      section.className = 'metadata-section';
      const list = element('ul');
      for (const value of values) list.append(element('li', value));
      section.append(element('h4', label), list);
      record.append(section);
    }
    results.append(record);
  }

  async function inspectRecord(kind) {
    if (submit.disabled || form.dataset.busy === 'true') return;
    const id = recordIdField.value.trim();
    const selectionVersion = recordSelectionVersion;
    const output = $('record-output-' + kind);
    const results = output.querySelector('.record-results');
    const feedback = output.querySelector('summary [role="status"]');
    const showFeedback = (message, tone = 'info') => {
      if (selectionVersion !== recordSelectionVersion) return;
      feedback.dataset.tone = tone;
      feedback.textContent = message;
    };
    for (const panel of document.querySelectorAll('.record-output[open]')) {
      if (panel !== output) panel.open = false;
    }
    setRequestId(kind);
    output.hidden = false;
    output.open = true;
    output.dataset.accordionState = 'loading';
    const countLabel = output.querySelector('.accordion-count');
    countLabel.textContent = '';
    showFeedback('');
    const loading = element('p', 'Loading…');
    loading.className = 'record-loading';
    loading.setAttribute('role', 'status');
    results.replaceChildren(loading);
    setAccordionState('record-raw', 'loading');
    $('record-raw-label').textContent = kind === 'metadata' ? 'Raw metadata JSON' : 'Raw record tool result';
    setBusy(form, true);
    try {
      const data = await api('/api/' + kind, {record_id: id}, requestId => {
        if (selectionVersion === recordSelectionVersion) setRequestId(kind, requestId);
      });
      if (selectionVersion !== recordSelectionVersion) return;
      let count;
      if (kind === 'image-assets') {
        const imageCount = data.images.length;
        count = imageCount + (imageCount === 1 ? ' image' : ' images');
        if (data.status === 'partial') {
          showFeedback(imageCount ? 'Some sources could not be checked.' : 'Image search incomplete.', 'warning');
        }
        showAssets(data, results);
      } else {
        count = '1 record';
        showMetadata(data, id, results);
      }
      countLabel.textContent = count;
      output.dataset.accordionState = data.status === 'partial' && kind === 'image-assets' ? 'partial' : 'ready';
      setAccordionState('record-raw', 'ready', pretty(data), '1 record');
    } catch (error) {
      if (selectionVersion === recordSelectionVersion) {
        output.open = true;
        output.dataset.accordionState = 'error';
        setAccordionState('record-raw', 'empty');
        showFeedback(error.message, 'error');
      }
    } finally {
      loading.remove();
      setBusy(form, false);
    }
  }

  const recordIdError = $('record-id-error');
  recordIdField.addEventListener('invalid', event => {
    event.preventDefault();
    recordIdField.setAttribute('aria-invalid', 'true');
    recordIdError.textContent = 'Enter a lowercase nmah_ followed by digits, for example nmah_446333.';
  });

  recordIdField.addEventListener('input', () => {
    if (recordIdField.validity.valid || !recordIdField.value) {
      recordIdField.removeAttribute('aria-invalid');
      recordIdError.textContent = '';
    }
    const id = recordIdField.value.trim();
    if (id !== selectedRecordId) {
      selectedRecordId = id;
      recordSelectionVersion += 1;
      setRequestId('image-assets');
      setRequestId('metadata');
      for (const output of document.querySelectorAll('.record-output')) {
        output.hidden = true;
        output.open = false;
        const feedback = output.querySelector('summary [role="status"]');
        delete output.dataset.accordionState;
        output.querySelector('.accordion-count').textContent = '';
        feedback.textContent = '';
        output.querySelector('.record-results').replaceChildren();
      }
      setAccordionState('record-raw', 'empty');
      $('record-raw-label').textContent = 'Raw record tool result';
    }
  });
  $('record-modes').addEventListener('change', updateActions);
  form.addEventListener('submit', event => {
    event.preventDefault();
    inspectRecord(form.elements['record-mode'].value);
  });

  return {selectRecord, updateActions};
}
