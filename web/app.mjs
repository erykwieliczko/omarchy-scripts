export const components = [
  { code: 'P', name: 'KDE Plasma' },
  { code: 'G', name: 'GNOME + GDM' },
  { code: 'K', name: 'Apple keyboard settings' },
  { code: 'S', name: 'Steam + AoE2 patches' },
  { code: 'H', name: 'SSH password login' },
];

export const installerURL = 'https://erykwieliczko.github.io/omarchy-scripts/install.sh';

const DEFAULT_OPTIONS = 'PK';
const DESKTOPS = ['P', 'G'];

// Returns the selection in canonical PGKSH order, '' for an empty selection,
// or null when the value contains anything unknown or both desktops.
// The explicit character class (instead of /i) keeps Unicode case-mapping
// tricks such as 'ſ' -> 'S' from sneaking through.
export function normalizeOptions(value) {
  if (typeof value !== 'string' || !/^[PGKSHpgksh]*$/.test(value)) return null;
  const upper = value.toUpperCase();
  if (upper.includes('P') && upper.includes('G')) return null;
  return components.map(component => component.code).filter(code => upper.includes(code)).join('');
}

export function installCommand(options) {
  const selected = normalizeOptions(options);
  return selected ? `curl -fsSL ${installerURL} | bash -s -- --options=${selected}` : '';
}

if (typeof document !== 'undefined') {
  const inputs = [...document.querySelectorAll('input[name="component"]')];
  const command = document.getElementById('install-command');
  const copyButton = document.getElementById('copy-command');
  const copyLabel = copyButton.querySelector('span');
  const linkButton = document.getElementById('copy-link');
  const feedback = document.getElementById('feedback');
  const selectedList = document.getElementById('selected-components');
  const selectionCode = document.getElementById('selection-code');
  const selectionCount = document.getElementById('selection-count');
  let labelTimer;

  const selectedOptions = () => normalizeOptions(inputs.filter(input => input.checked).map(input => input.value).join('')) ?? '';
  const nameOf = code => components.find(component => component.code === code)?.name ?? code;

  function say(message, tone = 'info') {
    feedback.textContent = message;
    feedback.dataset.tone = tone;
  }

  function resetCopyLabel() {
    clearTimeout(labelTimer);
    copyLabel.textContent = 'Copy command';
  }

  function render(updateURL = false) {
    const options = selectedOptions();
    const selected = components.filter(component => options.includes(component.code));
    const text = installCommand(options);

    command.textContent = text || 'Select at least one option to generate a command.';
    command.classList.toggle('is-empty', !text);
    selectionCode.textContent = options || '—';
    selectionCount.textContent = `${selected.length} selected`;
    copyButton.disabled = linkButton.disabled = selected.length === 0;
    resetCopyLabel();

    selectedList.replaceChildren(...selected.map(component => {
      const item = document.createElement('li');
      item.textContent = component.name;
      return item;
    }));
    if (!selected.length) {
      const empty = document.createElement('li');
      empty.className = 'is-empty';
      empty.textContent = 'Nothing selected';
      selectedList.append(empty);
    }

    say('');
    if (updateURL) {
      const url = new URL(window.location.href);
      url.searchParams.set('options', options);
      history.replaceState(null, '', url);
    }
  }

  function restoreSelection() {
    const query = new URL(window.location.href).searchParams.get('options');
    const options = query === null ? DEFAULT_OPTIONS : normalizeOptions(query);
    inputs.forEach(input => { input.checked = options?.includes(input.value) ?? false; });
    render();
    if (options === null) say('This link contains an unrecognized option, so nothing was selected. Choose your options above.', 'error');
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return false;
    }
  }

  inputs.forEach(input => input.addEventListener('change', () => {
    let replaced = null;
    if (input.checked && DESKTOPS.includes(input.value)) {
      inputs.forEach(other => {
        if (other !== input && DESKTOPS.includes(other.value) && other.checked) {
          other.checked = false;
          replaced = other.value;
        }
      });
    }
    render(true);
    if (replaced) say(`${nameOf(replaced)} deselected. Only one default desktop can be selected.`);
  }));

  window.addEventListener('popstate', restoreSelection);

  copyButton.addEventListener('click', async () => {
    const text = installCommand(selectedOptions());
    if (!text) return;
    if (await copyText(text)) {
      copyLabel.textContent = 'Copied';
      say('Command copied. Paste it into a terminal on your Omarchy install.', 'success');
      clearTimeout(labelTimer);
      labelTimer = setTimeout(resetCopyLabel, 2000);
    } else {
      // Select the real command so manual copying still works when clipboard
      // access is denied, without pretending that a copy succeeded.
      const range = document.createRange();
      range.selectNodeContents(command);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      say('Clipboard access is unavailable. The command is selected — copy it manually.', 'error');
    }
  });

  linkButton.addEventListener('click', async () => {
    const options = selectedOptions();
    if (!options) return;
    const url = new URL(window.location.href);
    url.searchParams.set('options', options);
    url.hash = '';
    if (await copyText(url.href)) {
      say('Link copied. It opens this page with the same selection.', 'success');
    } else {
      say(`Clipboard access is unavailable. Copy this link manually: ${url.href}`, 'error');
    }
  });

  restoreSelection();
}
