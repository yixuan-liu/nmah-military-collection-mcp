const $ = id => document.getElementById(id);

export function initJsonViewer({element, bindClearableField}) {
  function renderJson(output, content) {
    const tokens = /("(?:\\.|[^"\\])*")(?=\s*:)|("(?:\\.|[^"\\])*")|(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)|(true|false)|(null)/g;
    const kinds = ['key', 'string', 'number', 'boolean', 'null'];
    const fragment = document.createDocumentFragment();
    let end = 0;
    for (const match of content.matchAll(tokens)) {
      if (match.index > end) fragment.append(content.slice(end, match.index));
      const token = element('span', match[0]);
      token.className = 'json-' + kinds[match.slice(1).findIndex(value => value !== undefined)];
      fragment.append(token);
      end = match.index + match[0].length;
    }
    if (end < content.length) fragment.append(content.slice(end));
    output.replaceChildren(fragment);
  }

  function bindJsonSearch(dialog, output) {
    const form = dialog.querySelector('.json-find');
    bindClearableField(form.querySelector('.clearable-field'));
    const input = form.querySelector('input');
    const previous = form.querySelector('[data-previous-match]');
    const next = form.querySelector('button[type="submit"]');
    const status = form.querySelector('[role="status"]');
    let matches = [];
    let active = -1;

    function showMatch(index) {
      if (!matches.length) return;
      matches[active]?.removeAttribute('aria-current');
      active = (index + matches.length) % matches.length;
      const match = matches[active];
      match.setAttribute('aria-current', 'true');
      match.scrollIntoView({block: 'nearest', inline: 'nearest'});
      status.textContent = (active + 1) + ' of ' + matches.length;
    }

    function updateMatches() {
      const query = input.value;
      const pattern = query ? new RegExp(query.replace(/[.*+?^$(){}[\]\\]/g, '\\$&'), 'giu') : null;
      for (const mark of matches) mark.replaceWith(mark.textContent);
      matches = [];
      active = -1;

      if (pattern) {
        for (const token of output.querySelectorAll('.json-key, .json-string, .json-number, .json-boolean, .json-null')) {
          const text = token.textContent;
          const hits = [...text.matchAll(pattern)];
          if (!hits.length) continue;
          const fragment = document.createDocumentFragment();
          let end = 0;
          for (const hit of hits) {
            if (hit.index > end) fragment.append(text.slice(end, hit.index));
            const mark = element('mark', hit[0]);
            mark.className = 'json-match';
            fragment.append(mark);
            matches.push(mark);
            end = hit.index + hit[0].length;
          }
          if (end < text.length) fragment.append(text.slice(end));
          token.replaceChildren(fragment);
        }
      }

      previous.disabled = next.disabled = !matches.length;
      if (matches.length) showMatch(0);
      else status.textContent = query ? 'No matches' : '';
    }

    input.addEventListener('input', updateMatches);
    input.addEventListener('keydown', event => {
      if (event.isComposing) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        dialog.close();
      } else if (event.key === 'Enter' && event.shiftKey) {
        event.preventDefault();
        showMatch(active - 1);
      }
    });
    previous.addEventListener('click', () => showMatch(active - 1));
    form.addEventListener('submit', event => {
      event.preventDefault();
      showMatch(active + 1);
    });
    dialog.addEventListener('close', () => {
      input.value = '';
      input.dispatchEvent(new Event('input'));
    });
  }

  function setCopyState(action, state = 'idle', label = 'JSON') {
    action.toggleAttribute('data-copied', state === 'copied');
    action.querySelector('button').setAttribute(
      'aria-label', state === 'copied' && label === 'JSON' ? 'Reset JSON copy status' : 'Copy ' + label
    );
    action.querySelector('.help-tooltip').textContent =
      state === 'copied' ? 'Copied' : state === 'failed' ? 'Copy failed' : 'Copy';
  }

  function setRequestId(panel, requestId) {
    const row = $(panel + '-request-id');
    row.querySelector('code').textContent = requestId || '';
    row.hidden = !requestId;
    setCopyState(row.querySelector('.copy-action'), 'idle', 'request ID');
  }

  for (const row of document.querySelectorAll('.request-id-row')) {
    const template = $('accordion-copy-template');
    const action = template.content.querySelector('.json-copy-action').cloneNode(true);
    action.classList.remove('json-copy-action');
    setCopyState(action, 'idle', 'request ID');
    row.append(action);
    const code = row.querySelector('code');
    let feedbackTimer;
    action.querySelector('button').addEventListener('click', async () => {
      const requestId = code.textContent;
      if (!requestId) return;
      clearTimeout(feedbackTimer);
      let state = 'copied';
      try {
        await navigator.clipboard.writeText(requestId);
      } catch {
        state = 'failed';
      }
      if (code.textContent !== requestId) return;
      setCopyState(action, state, 'request ID');
      feedbackTimer = setTimeout(() => {
        if (code.textContent === requestId) setCopyState(action, 'idle', 'request ID');
      }, 1800);
    });
  }

  function setAccordionState(id, state, content = '', count = '') {
    const output = $(id);
    renderJson(output, content);
    const accordion = output.closest('details');
    accordion.dataset.accordionState = state;
    const countLabel = accordion.querySelector(':scope > summary > .accordion-count');
    if (countLabel) countLabel.textContent = count;
    setCopyState(accordion.querySelector('.json-copy-action'));
    const dialog = accordion.querySelector('.json-dialog');
    if (state !== 'ready' && dialog.open) dialog.close();
  }

  for (const output of document.querySelectorAll('details[data-accordion-state] > pre')) {
    const template = $('accordion-copy-template').content.cloneNode(true);
    const controls = template.querySelector('.accordion-copy-tools');
    const action = controls.querySelector('.json-copy-action');
    const expand = controls.querySelector('[data-expand-json]');
    const dialog = template.querySelector('dialog');
    const close = dialog.querySelector('[data-close-json]');
    const title = dialog.querySelector('h2');
    const summary = output.closest('details').querySelector('summary');
    title.id = output.id + '-fullscreen-title';
    dialog.setAttribute('aria-labelledby', title.id);
    bindJsonSearch(dialog, output);
    let copying = false;

    action.querySelector('button').addEventListener('click', async () => {
      if (action.hasAttribute('data-copied')) {
        setCopyState(action);
        return;
      }
      const content = output.textContent;
      if (copying || !content) return;
      const rendered = output.firstChild;
      copying = true;
      setCopyState(action);
      try {
        await navigator.clipboard.writeText(content);
        if (output.firstChild === rendered) setCopyState(action, 'copied');
      } catch {
        if (output.firstChild === rendered) setCopyState(action, 'failed');
      } finally {
        copying = false;
      }
    });
    const viewer = element('div');
    viewer.className = 'accordion-json';
    output.before(viewer);
    viewer.append(controls, output, dialog);

    let inlineScrollTop = 0;
    expand.addEventListener('click', () => {
      inlineScrollTop = output.scrollTop;
      title.textContent = summary.firstChild.textContent.trim();
      dialog.querySelector('.json-dialog-actions').prepend(action);
      dialog.append(output);
      output.tabIndex = 0;
      dialog.showModal();
      output.scrollTop = 0;
      dialog.querySelector('.json-find input').focus();
    });
    close.addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
      controls.prepend(action);
      viewer.insertBefore(output, dialog);
      output.removeAttribute('tabindex');
      output.scrollTop = inlineScrollTop;
      expand.focus();
    });
  }

  return {setAccordionState, setRequestId};
}
