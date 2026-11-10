import { api } from './api.js';

const $ = id => document.getElementById(id);
const pretty = data => JSON.stringify(data, null, 2);

export function initSearch({element, setAccordionState, setBusy, setRequestId, updateAction, onInspect}) {
  const searchForm = $('search-form');
  const submit = searchForm.querySelector('button[type="submit"]');

  let pageLinks = null;
  let pagedSearch = null;
  let manualOffset = $('offset').value;

  function updateSearchActions() {
    const searching = searchForm.dataset.busy === 'true';
    updateAction(submit, searching);
    $('search-pagination').hidden = pageLinks === null;
    $('search-page-label').textContent = pageLinks?.label ?? '';
    for (const direction of ['previous', 'next']) {
      const button = $(direction + '-page');
      updateAction(button, searching || pageLinks?.[direction] == null);
    }
  }

  function searchArguments() {
    return {
      query: $('query').value,
      branch: $('branch').value || null,
      date: $('date').value || null,
      has_images: $('has-images').checked,
      rows: $('rows').valueAsNumber,
      offset: $('offset').valueAsNumber,
    };
  }

  function sameSearchCriteria(first, second) {
    return ['query', 'branch', 'date', 'has_images', 'rows'].every(key => first[key] === second[key]);
  }

  async function search(arguments_) {
    if (submit.disabled || searchForm.dataset.busy === 'true') return;
    const initialFocus = document.activeElement;
    pageLinks = null;
    const status = $('search-status');
    delete status.dataset.tone;
    status.textContent = '';
    const records = $('search-output');
    setRequestId('search');
    records.open = true;
    records.dataset.accordionState = 'loading';
    const count = records.querySelector('.accordion-count');
    count.textContent = '';
    $('search-table').hidden = true;
    $('search-results').replaceChildren();
    setAccordionState('search-raw', 'loading');
    setAccordionState('search-query', 'loading');
    setBusy(searchForm, true);
    try {
      const page = await api('/api/search', arguments_, id => setRequestId('search', id));
      status.textContent = 'Total: ' + page.total_count.toLocaleString();
      const pageCount = page.objects.length;
      const recordCount = pageCount + (pageCount === 1 ? ' record' : ' records');
      setAccordionState('search-raw', 'ready', pretty(page), recordCount);
      setAccordionState('search-query', 'ready', pretty({query: page.applied_query, filters: page.applied_filters, offset: page.offset}));
      for (const row of page.objects) {
        const id = row.content?.descriptiveNonRepeating?.record_ID;
        const tr = element('tr');
        tr.append(element('td', id || 'Unknown'), element('td', row.title || 'Untitled'));
        const actions = element('td');
        actions.className = 'search-row-action';
        if (id) {
          const use = element('button', 'Inspect');
          use.type = 'button';
          use.setAttribute('aria-label', 'Inspect ' + id);
          use.addEventListener('click', () => onInspect(id));
          actions.append(use);
        }
        tr.append(actions);
        $('search-results').append(tr);
      }
      $('search-table').hidden = pageCount === 0;
      $('search-empty').querySelector('small').textContent = 'No records on this page.';
      records.dataset.accordionState = pageCount ? 'ready' : 'empty';
      count.textContent = recordCount;
      const current = searchArguments();
      if (page.total_count > 0 && sameSearchCriteria(arguments_, current) && arguments_.offset === current.offset) {
        const {rows} = arguments_;
        const {offset, total_count: total} = page;
        const totalPages = Math.ceil(total / rows);
        let label;
        if (!pageCount) {
          label = 'No records at offset ' + offset.toLocaleString();
        } else if (offset % rows === 0) {
          label = 'Page ' + (offset / rows + 1).toLocaleString() + ' of ' + totalPages.toLocaleString();
        } else {
          label = 'Records ' + (offset + 1).toLocaleString() + '–' +
            (offset + pageCount).toLocaleString() + ' of ' + total.toLocaleString();
        }
        pageLinks = {
          criteria: arguments_,
          label,
          previous: offset > 0 ? Math.min(Math.max(0, offset - rows), (totalPages - 1) * rows) : null,
          next: page.next_offset ?? null,
        };
      }
    } catch (error) {
      records.open = true;
      records.dataset.accordionState = 'error';
      setAccordionState('search-raw', 'empty');
      setAccordionState('search-query', 'empty');
      status.dataset.tone = 'error';
      status.textContent = error.message;
    } finally {
      setBusy(searchForm, false);
      if (document.activeElement === document.body || document.activeElement === initialFocus) {
        $('search-results-title').focus();
      }
    }
  }

  const paginationOptions = $('search-pagination-options');
  paginationOptions.addEventListener('invalid', () => { paginationOptions.open = true; }, true);
  searchForm.addEventListener('submit', event => {
    event.preventDefault();
    search(searchArguments());
  });
  searchForm.addEventListener('input', event => {
    if (event.target === $('offset')) {
      manualOffset = $('offset').value;
      pagedSearch = null;
      pageLinks = null;
      updateSearchActions();
      return;
    }
    const criteria = searchArguments();
    if (pagedSearch && !sameSearchCriteria(pagedSearch, criteria)) {
      $('offset').value = manualOffset;
      pagedSearch = null;
    }
    if (pageLinks && !sameSearchCriteria(pageLinks.criteria, criteria)) {
      pageLinks = null;
      updateSearchActions();
    }
  });
  for (const direction of ['previous', 'next']) {
    $(direction + '-page').addEventListener('click', () => {
      const offset = pageLinks?.[direction];
      if (offset == null) return;
      pagedSearch = {...pageLinks.criteria, offset};
      $('offset').value = offset;
      search(pagedSearch);
    });
  }

  return updateSearchActions;
}
