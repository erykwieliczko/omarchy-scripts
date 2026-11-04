export const components = [
  { code: 'P', name: 'KDE Plasma' },
  { code: 'K', name: 'Apple keyboard settings' },
  { code: 'S', name: 'Steam + AoE2 patches' },
];

export const installerURL = 'https://erykwieliczko.github.io/omarchy-scripts/install.sh';

export function normalizeOptions(value) {
  const upper = value.toUpperCase();
  if (!/^[PKS]*$/.test(upper)) return null;
  return components.filter(component => upper.includes(component.code)).map(component => component.code).join('');
}

export function installCommand(options) {
  const selected = normalizeOptions(options);
  return selected ? `curl -fsSL ${installerURL} | bash -s -- --options=${selected}` : '';
}

if (typeof document !== 'undefined') {
  const inputs = [...document.querySelectorAll('input[name="component"]')];
  const command = document.getElementById('install-command');
  const copyButton = document.getElementById('copy-command');
  const linkButton = document.getElementById('copy-link');
  const feedback = document.getElementById('feedback');
  const selectedList = document.getElementById('selected-components');
  const selectionCode = document.getElementById('selection-code');
  const selectionCount = document.getElementById('selection-count');

  const selectedOptions = () => inputs.filter(input => input.checked).map(input => input.value).join('');

  function render(updateURL = false) {
    const options = selectedOptions();
    const selected = components.filter(component => options.includes(component.code));
    command.textContent = installCommand(options) || 'Choose at least one component to create your command.';
    selectionCode.textContent = options || '—';
    selectionCount.textContent = `${selected.length} selected`;
    copyButton.disabled = linkButton.disabled = selected.length === 0;
    copyButton.querySelector('span').textContent = 'Copy command';
    selectedList.replaceChildren();
    selected.forEach(component => {
      const item = document.createElement('li');
      item.textContent = component.name;
      selectedList.append(item);
    });
    if (!selected.length) {
      const empty = document.createElement('li');
      empty.textContent = 'Choose what feels right for you.';
      empty.className = 'empty-plan';
      selectedList.append(empty);
    }
    feedback.textContent = '';
    if (updateURL) {
      const url = new URL(window.location.href);
      url.searchParams.set('options', options);
      history.replaceState(null, '', url);
    }
  }

  function restoreSelection() {
    const query = new URL(window.location.href).searchParams.get('options');
    const options = query === null ? 'PK' : normalizeOptions(query);
    inputs.forEach(input => { input.checked = options?.includes(input.value) ?? false; });
    render();
    if (options === null) feedback.textContent = 'That link contains an unknown option. Choose your configuration above.';
  }

  async function copyText(text, message) {
    try {
      await navigator.clipboard.writeText(text);
      feedback.textContent = message;
      return true;
    } catch {
      // Select the real command so keyboard copying still works if clipboard
      // access is denied, without pretending that a copy succeeded.
      const range = document.createRange();
      range.selectNodeContents(command);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      feedback.textContent = 'Clipboard access is unavailable. Select and copy the command above.';
      return false;
    }
  }

  inputs.forEach(input => input.addEventListener('change', () => render(true)));
  window.addEventListener('popstate', restoreSelection);
  copyButton.addEventListener('click', async () => {
    if (await copyText(installCommand(selectedOptions()), 'Command copied. Paste it into your Omarchy terminal.')) {
      copyButton.querySelector('span').textContent = 'Copied!';
    }
  });
  linkButton.addEventListener('click', () => {
    const url = new URL(window.location.href);
    url.searchParams.set('options', selectedOptions());
    url.hash = '';
    copyText(url.href, 'Setup link copied. It remembers your selected components.');
  });
  restoreSelection();
}
