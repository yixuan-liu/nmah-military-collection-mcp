import { api } from './api.js';

const $ = id => document.getElementById(id);

export function initToolConnections({element, setAccordionState, toolLabels, onConnectionsChange, onToolsDiscovered}) {
  const tools = new Map();
  const connectedTools = new Set();
  const reconnectingTools = new Set();
  const pretty = data => JSON.stringify(data, null, 2);

  function getState(name) {
    if (reconnectingTools.has(name)) return 'connecting';
    if (connectedTools.has(name)) return 'connected';
    return tools.has(name) ? 'disconnected' : 'unavailable';
  }

  function showSchema() {
    const tool = tools.get($('tool').value);
    if (tool) {
      setAccordionState('schema', 'ready', pretty({inputSchema: tool.inputSchema, outputSchema: tool.outputSchema}));
    } else {
      setAccordionState('schema', 'empty');
    }
  }

  function updateConnections() {
    $('connection').textContent = connectedTools.size + ' of ' + tools.size + ' connected';
    onConnectionsChange();
  }

  function toolConnectionRow(name, label) {
    const row = element('li');
    row.className = 'tool-connection-row';
    const identity = element('div');
    identity.className = 'tool-connection-identity';
    const dot = element('span');
    dot.className = 'tool-connection-dot';
    dot.setAttribute('aria-hidden', 'true');
    const status = element('span');
    status.className = 'tool-connection-state';
    status.setAttribute('role', 'status');
    const title = element('span', label);
    title.className = 'tool-connection-name';
    identity.append(dot, title, status);

    const toolId = element('code', name);
    toolId.className = 'tool-connection-id';

    const action = element('button');
    action.type = 'button';
    action.className = 'tool-connection-action';
    const error = element('p');
    error.className = 'tool-connection-error';
    error.setAttribute('role', 'alert');
    error.hidden = true;

    function showState(state, label, actionLabel) {
      dot.dataset.state = state;
      status.textContent = label;
      action.textContent = actionLabel;
      action.setAttribute('aria-label', actionLabel + ' ' + name);
    }

    showState('connected', 'Connected', 'Disconnect');
    action.addEventListener('click', async () => {
      error.hidden = true;
      if (connectedTools.delete(name)) {
        showState('disconnected', 'Disconnected', 'Connect');
        updateConnections();
        return;
      }

      action.disabled = true;
      reconnectingTools.add(name);
      showState('connecting', 'Connecting…', 'Connect');
      onConnectionsChange();
      const slowConnection = setTimeout(() => {
        status.textContent = 'Still waiting for MCP…';
      }, 3000);
      try {
        const discovery = await api('/api/schema');
        const tool = discovery.tools.find(entry => entry.name === name);
        if (!tool) throw new Error('MCP no longer lists this tool.');
        tools.set(name, tool);
        connectedTools.add(name);
        showState('connected', 'Connected', 'Disconnect');
        showSchema();
      } catch (failure) {
        showState('disconnected', 'Disconnected', 'Connect');
        error.textContent = failure.message;
        error.hidden = false;
      } finally {
        clearTimeout(slowConnection);
        reconnectingTools.delete(name);
        action.disabled = false;
        updateConnections();
      }
    });
    row.append(identity, action, toolId, error);
    return row;
  }

  const connectionMenu = document.querySelector('.connection');
  connectionMenu.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || !connectionMenu.open) return;
    connectionMenu.open = false;
    connectionMenu.querySelector('summary').focus();
  });

  const schemaSummary = $('schema-summary');
  schemaSummary.addEventListener('click', event => {
    if (schemaSummary.getAttribute('aria-disabled') === 'true') event.preventDefault();
  });
  $('tool').addEventListener('change', showSchema);

  function discover() {
    setAccordionState('schema', 'loading');
    api('/api/schema').then(result => {
      $('connected-tools').replaceChildren();
      if (!result.tools.length) {
        const empty = element('li');
        empty.className = 'accordion-empty';
        empty.append(element('strong', 'No data'), element('small', 'No MCP tools were found. Refresh the page to check again.'));
        $('connected-tools').append(empty);
      }
      for (const tool of result.tools) {
        tools.set(tool.name, tool);
        connectedTools.add(tool.name);
        const label = toolLabels[tool.name] || tool.name;
        $('connected-tools').append(toolConnectionRow(tool.name, label));
        $('tool').add(new Option(label, tool.name));
      }
      onToolsDiscovered(tools);
      updateConnections();
      showSchema();
    }).catch(error => {
      setAccordionState('schema', 'empty');
      $('connection').textContent = 'Unavailable';
      $('connected-tools').replaceChildren(element('li', error.message));
    }).finally(() => {
      schemaSummary.removeAttribute('aria-disabled');
      schemaSummary.removeAttribute('tabindex');
    });
  }

  return {discover, getState};
}
