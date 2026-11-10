import { api } from './api.js';

const $ = id => document.getElementById(id);

export function initApiKey({onStatusChange}) {
  let apiKeyStatus;
  const keyDialog = $('api-key-dialog');
  const keyInput = $('api-key-input');
  let keyBusy = false;
  let showSearchHandoff = false;
  let keyStatusRequest = 0;
  let keyInputRevision = 0;
  let storedKeyVisible = false;
  let copyResetTimer;

  function showKeyFeedback(message, error = false) {
    const feedback = $('key-feedback');
    feedback.toggleAttribute('data-error', error);
    feedback.textContent = message;
  }

  function updateKeyControls() {
    const hasCandidate = !storedKeyVisible && Boolean(keyInput.value.trim());
    const hasKeyToCopy = hasCandidate || apiKeyStatus?.configured;
    keyInput.placeholder = apiKeyStatus?.configured ? '••••••••••••' : '';
    const apply = $('apply-api-key');
    const continueToSearch = showSearchHandoff && apiKeyStatus?.configured && !hasCandidate;
    $('continue-to-search').hidden = !continueToSearch;
    $('continue-to-search').disabled = keyBusy;
    apply.hidden = continueToSearch;
    apply.disabled = keyBusy || continueToSearch || (!hasCandidate && !apiKeyStatus?.configured);
    apply.textContent = hasCandidate || !apiKeyStatus?.configured ? 'Verify and apply' : 'Verify current key';
    $('use-default-key').hidden = apiKeyStatus?.source !== 'debugger';
    $('use-default-key').disabled = keyBusy;
    $('close-api-key').disabled = keyBusy;
    $('show-api-key').disabled = keyBusy;
    $('copy-api-key').disabled = keyBusy || !hasKeyToCopy;
    if (copyResetTimer === undefined) {
      $('key-copy-hint').textContent = 'Copy';
    }
    keyInput.disabled = keyBusy;
  }

  function showKeyState(label, verified = false) {
    const state = $('key-state');
    state.textContent = label;
    state.toggleAttribute('data-verified', verified);
  }

  function renderKeyStatus(status) {
    apiKeyStatus = status;
    const trigger = $('open-api-key');
    trigger.toggleAttribute('data-missing', !status.configured);
    trigger.textContent = status.configured ? 'API key' : 'API key required';
    const label = status.verified ? 'Verified' : status.configured ? 'Configured · Not verified' : 'Not configured';
    showKeyState(label, status.verified);
    $('key-source').textContent = status.source === 'debugger' ? 'Playground override' : '';
    updateKeyControls();
    onStatusChange();
  }

  async function refreshKeyStatus() {
    const request = ++keyStatusRequest;
    try {
      const status = await api('/api/api-key');
      if (request === keyStatusRequest) renderKeyStatus(status);
    } catch (error) {
      if (request !== keyStatusRequest) return;
      showKeyState('Configuration unavailable');
      showKeyFeedback(error.message, true);
    }
  }

  async function changeApiKey(arguments_, reset = false) {
    if (keyBusy) return;
    const firstSetup = !apiKeyStatus?.configured && !reset;
    keyBusy = true;
    keyStatusRequest += 1;
    keyInputRevision += 1;
    updateKeyControls();
    showKeyFeedback(reset ? 'Restoring project default…' : '');
    if (!reset) showKeyState('Verifying…');
    try {
      const status = await api('/api/api-key', arguments_);
      showSearchHandoff = !reset && status.verified && (firstSetup || showSearchHandoff);
      keyInput.value = '';
      storedKeyVisible = false;
      setKeyVisibility(false);
      clearCopyFeedback();
      renderKeyStatus(status);
      showKeyFeedback(reset ? 'Playground override cleared.' : '');
    } catch (error) {
      if (!reset) showKeyState('Verification failed');
      showKeyFeedback(error.message, true);
    } finally {
      keyBusy = false;
      updateKeyControls();
      const handoff = $('continue-to-search');
      (handoff.hidden ? keyInput : handoff).focus();
    }
  }

  function openKeyDialog() {
    showKeyFeedback('');
    keyDialog.showModal();
    refreshKeyStatus();
  }
  $('open-api-key').addEventListener('click', openKeyDialog);
  $('search-open-api-key').addEventListener('click', openKeyDialog);
  $('close-api-key').addEventListener('click', () => keyDialog.close());
  $('continue-to-search').addEventListener('click', () => {
    keyDialog.close();
    $('query').focus();
  });
  keyDialog.addEventListener('cancel', event => {
    if (keyBusy) event.preventDefault();
  });
  keyDialog.addEventListener('close', () => {
    showSearchHandoff = false;
    keyInputRevision += 1;
    keyInput.value = '';
    storedKeyVisible = false;
    setKeyVisibility(false);
    clearCopyFeedback();
  });
  function setKeyVisibility(reveal) {
    const label = reveal ? 'Hide API key' : 'Show API key';
    keyInput.type = reveal ? 'text' : 'password';
    $('show-api-key').setAttribute('aria-label', label);
    $('key-visibility-hint').textContent = reveal ? 'Hide' : 'Show';
    $('key-eye').toggleAttribute('hidden', reveal);
    $('key-eye-off').toggleAttribute('hidden', !reveal);
  }

  function clearCopyFeedback() {
    clearTimeout(copyResetTimer);
    copyResetTimer = undefined;
    $('copy-api-key').parentElement.removeAttribute('data-copied');
    $('key-copy-icon').removeAttribute('hidden');
    $('key-copy-done').setAttribute('hidden', '');
    updateKeyControls();
  }

  async function revealStoredKey() {
    const {key} = await api('/api/api-key', {reveal: true});
    return key;
  }

  keyInput.addEventListener('input', () => {
    keyInputRevision += 1;
    storedKeyVisible = false;
    showKeyFeedback('');
    clearCopyFeedback();
  });
  $('show-api-key').addEventListener('click', async () => {
    const reveal = keyInput.type === 'password';
    const revision = ++keyInputRevision;
    if (!reveal && storedKeyVisible) {
      keyInput.value = '';
      storedKeyVisible = false;
    }
    if (reveal && !keyInput.value && apiKeyStatus?.configured) {
      try {
        const key = await revealStoredKey();
        if (!keyDialog.open || revision !== keyInputRevision) return;
        keyInput.value = key;
        storedKeyVisible = true;
      } catch {
        if (keyDialog.open && revision === keyInputRevision) showKeyFeedback('Could not show the configured API key.', true);
        return;
      }
    }
    setKeyVisibility(reveal);
    updateKeyControls();
  });
  $('copy-api-key').addEventListener('click', async () => {
    const revision = keyInputRevision;
    try {
      const key = keyInput.value.trim() ? keyInput.value : await revealStoredKey();
      if (!keyDialog.open || revision !== keyInputRevision) return;
      await navigator.clipboard.writeText(key);
      if (!keyDialog.open || revision !== keyInputRevision) return;
      clearTimeout(copyResetTimer);
      $('copy-api-key').parentElement.setAttribute('data-copied', '');
      $('key-copy-icon').setAttribute('hidden', '');
      $('key-copy-done').removeAttribute('hidden');
      $('key-copy-hint').textContent = 'Copied';
      showKeyFeedback('API key copied.');
      copyResetTimer = setTimeout(() => {
        clearCopyFeedback();
        if ($('key-feedback').textContent === 'API key copied.') showKeyFeedback('');
      }, 1800);
    } catch {
      if (keyDialog.open && revision === keyInputRevision) {
        showKeyFeedback('Could not copy the API key. Show the key, then select and copy it from the field.', true);
      }
    }
  });
  $('key-form').addEventListener('submit', event => {
    event.preventDefault();
    const candidate = storedKeyVisible ? '' : keyInput.value.trim();
    if (candidate || apiKeyStatus?.configured) changeApiKey(candidate ? {key: candidate} : {});
  });
  $('use-default-key').addEventListener('click', () => changeApiKey({use_default: true}, true));

  window.addEventListener('focus', () => {
    if (!keyBusy) refreshKeyStatus();
  });

  return {getStatus: () => apiKeyStatus, refresh: refreshKeyStatus};
}
