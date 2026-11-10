import { initApiKey } from './api-key.js';
import { initImageViewer } from './image-viewer.js';
import { initInspect } from './inspect.js';
import { initJsonViewer } from './json-viewer.js';
import { initSearch } from './search.js';
import { initToolConnections } from './tool-connections.js';

const $ = id => document.getElementById(id);
const searchTool = 'search_nmah_military_objects';
const recordTools = {
  metadata: 'get_nmah_military_object_metadata',
  'image-assets': 'get_nmah_military_object_image_assets',
};
const toolLabels = {
  [searchTool]: 'Search objects',
  [recordTools.metadata]: 'Get metadata',
  [recordTools['image-assets']]: 'Get image assets',
};
function element(tag, value) {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  return node;
}

function resourceLink(url, label, showExternalIcon = false) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'https:' &&
        (parsed.hostname === 'si.edu' || parsed.hostname.endsWith('.si.edu') || parsed.hostname === 'n2t.net')) {
      const link = element('a', label);
      link.href = parsed.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      if (showExternalIcon) {
        const svgNamespace = 'http://www.w3.org/2000/svg';
        const icon = document.createElementNS(svgNamespace, 'svg');
        icon.setAttribute('viewBox', '0 0 16 16');
        icon.setAttribute('aria-hidden', 'true');
        icon.setAttribute('focusable', 'false');
        const arrow = document.createElementNS(svgNamespace, 'path');
        arrow.setAttribute('d', 'M4 12 12 4M6 4h6v6');
        arrow.setAttribute('fill', 'none');
        arrow.setAttribute('stroke', 'currentColor');
        arrow.setAttribute('stroke-width', '1.5');
        arrow.setAttribute('stroke-linecap', 'round');
        arrow.setAttribute('stroke-linejoin', 'round');
        icon.append(arrow);
        link.classList.add('external-link');
        link.append(icon);
      }
      return link;
    }
  } catch {}
  return element('span', label);
}

function updateToolAction(button, toolName, disabled) {
  const state = connections.getState(toolName);
  const configured = apiKey.getStatus()?.configured;
  const connected = state === 'connected';
  const missingKey = connected && configured === false;
  const unavailable = state === 'connecting' || state === 'disconnected' || missingKey;
  button.disabled = disabled || !connected || !configured;

  const wrapper = button.parentElement;
  const tooltip = wrapper.querySelector('.help-tooltip');
  const inlineKeySetup = missingKey && wrapper.classList.contains('tool-action-primary');
  tooltip.hidden = !unavailable || inlineKeySetup;
  if (unavailable) {
    if (missingKey) {
      wrapper.dataset.toolState = 'missing-key';
      tooltip.textContent = 'Set a Smithsonian API key to run this tool.';
    } else {
      wrapper.dataset.toolState = state;
      tooltip.textContent = state === 'connecting'
        ? 'Connecting to MCP…'
        : 'This MCP tool is disconnected. Reconnect it under MCP tool connections.';
    }
    wrapper.tabIndex = 0;
    wrapper.setAttribute('aria-describedby', inlineKeySetup ? 'search-key-setup' : tooltip.id);
  } else {
    delete wrapper.dataset.toolState;
    wrapper.removeAttribute('tabindex');
    wrapper.removeAttribute('aria-describedby');
  }
}

function updateToolActions() {
  $('search-key-setup').hidden = apiKey.getStatus()?.configured !== false;
  updateSearchActions();
  inspect.updateActions();
}

function setBusy(form, busy) {
  form.dataset.busy = String(busy);
  for (const button of form.querySelectorAll('button')) button.disabled = busy;
  updateToolActions();
}

function bindClearableField(group) {
  const field = group.querySelector('input');
  const clear = group.querySelector('.clear-field-button');
  const update = () => { clear.hidden = field.value.length === 0; };

  field.addEventListener('input', update);
  clear.addEventListener('click', () => {
    field.value = '';
    field.dispatchEvent(new Event('input'));
    field.focus();
  });
  update();
}

document.querySelectorAll('.clearable-field').forEach(bindClearableField);

for (const group of document.querySelectorAll('.field-with-help')) {
  const button = group.querySelector('.help-trigger');
  const tooltip = group.querySelector('.help-tooltip');
  let pinned = false;

  function close() {
    pinned = false;
    tooltip.hidden = true;
  }

  button.addEventListener('pointerenter', event => {
    if (event.pointerType === 'mouse') tooltip.hidden = false;
  });
  group.addEventListener('pointerleave', () => {
    if (!pinned && !button.matches(':focus-visible')) close();
  });
  button.addEventListener('focus', () => { tooltip.hidden = false; });
  button.addEventListener('blur', close);
  button.addEventListener('click', () => {
    if (pinned) close();
    else {
      pinned = true;
      tooltip.hidden = false;
    }
  });
  document.addEventListener('pointerdown', event => {
    if (!group.contains(event.target)) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !tooltip.hidden) close();
  });
}

const showAssets = initImageViewer({element, resourceLink});
const {setAccordionState, setRequestId} = initJsonViewer({element, bindClearableField});
const apiKey = initApiKey({onStatusChange: updateToolActions});
const connections = initToolConnections({
  element,
  setAccordionState,
  toolLabels,
  onConnectionsChange: updateToolActions,
  onToolsDiscovered(tools) {
    const props = tools.get(searchTool)?.inputSchema.properties;
    for (const key of ['branch', 'date']) {
      const values = props?.[key]?.anyOf?.find(choice => choice.enum)?.enum ?? [];
      for (const value of values) $(key).add(new Option(value));
    }
  },
});

const inspect = initInspect({
  element,
  resourceLink,
  setAccordionState,
  setBusy,
  setRequestId,
  showAssets,
  getToolState(kind) {
    const toolName = recordTools[kind];
    const state = connections.getState(toolName);
    const configured = apiKey.getStatus()?.configured;
    let hint = '';
    if (state === 'connecting') {
      hint = 'Connecting to MCP…';
    } else if (state === 'disconnected') {
      hint = 'This MCP tool is disconnected. Reconnect it under MCP tool connections.';
    } else if (configured === false) {
      hint = 'Set a Smithsonian API key to run this tool.';
    }
    return {label: toolLabels[toolName], available: state === 'connected' && configured, hint};
  },
});

const updateSearchActions = initSearch({
  element,
  setAccordionState,
  setBusy,
  setRequestId,
  updateAction: (button, disabled) => updateToolAction(button, searchTool, disabled),
  onInspect: inspect.selectRecord,
});

apiKey.refresh();
connections.discover();
