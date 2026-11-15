(() => {
  const dialog = document.createElement('dialog');
  dialog.className = 'feedback-modal';
  dialog.setAttribute('aria-labelledby', 'feedback-modal-title');
  dialog.setAttribute('aria-describedby', 'feedback-modal-message');
  dialog.innerHTML = `
    <div class="feedback-modal-content">
      <span class="feedback-modal-icon" aria-hidden="true"></span>
      <h2 id="feedback-modal-title"></h2>
      <p id="feedback-modal-message"></p>
      <label id="feedback-modal-input-label" class="hidden" for="feedback-modal-input"></label>
      <input id="feedback-modal-input" class="hidden" type="text" autocomplete="off">
      <div class="feedback-modal-actions"></div>
    </div>`;
  document.body.append(dialog);

  const title = dialog.querySelector('#feedback-modal-title');
  const message = dialog.querySelector('#feedback-modal-message');
  const icon = dialog.querySelector('.feedback-modal-icon');
  const inputLabel = dialog.querySelector('#feedback-modal-input-label');
  const input = dialog.querySelector('#feedback-modal-input');
  const actions = dialog.querySelector('.feedback-modal-actions');
  const queue = [];
  let resolveResult;
  let activePrompt = false;

  function close(result) {
    if (!dialog.open) return;
    dialog.close();
    if (resolveResult) resolveResult(result);
    resolveResult = null;
    activePrompt = false;
    setTimeout(openNext, 0);
  }

  function openNext() {
    if (dialog.open || !queue.length) return;
    const {text, options, resolve} = queue.shift();
    const type = options.type || 'error';
    activePrompt = Boolean(options.prompt);
    dialog.dataset.type = type;
    dialog.setAttribute('role', options.confirm || options.prompt ? 'alertdialog' : 'dialog');
    title.textContent = options.title || (type === 'success' ? 'Tudo certo!' : type === 'warning' ? 'Atenção' : 'Não foi possível concluir');
    message.textContent = text;
    icon.textContent = type === 'success' ? '✓' : type === 'warning' ? '!' : '×';
    inputLabel.textContent = options.inputLabel || 'Código';
    inputLabel.classList.toggle('hidden', !options.prompt);
    input.classList.toggle('hidden', !options.prompt);
    input.value = '';
    input.required = Boolean(options.prompt);
    input.pattern = options.pattern || '';
    input.maxLength = options.maxLength || 200;
    input.inputMode = options.inputMode || 'text';
    input.placeholder = options.placeholder || '';
    actions.replaceChildren();

    if (options.confirm || options.prompt) {
      const cancel = document.createElement('button');
      cancel.className = 'btn subtle';
      cancel.type = 'button';
      cancel.dataset.modalCancel = '';
      cancel.textContent = options.cancelLabel || 'Voltar';
      cancel.addEventListener('click', () => close(options.prompt ? null : false), {once: true});
      actions.append(cancel);
    }

    const accept = document.createElement('button');
    accept.className = 'btn primary';
    accept.type = 'button';
    accept.dataset.modalAccept = '';
    accept.textContent = options.confirm || options.prompt ? (options.confirmLabel || 'Confirmar') : 'Entendi';
    accept.addEventListener('click', () => {
      if (options.prompt) {
        close(input.value.trim());
      } else {
        close(options.confirm ? true : undefined);
      }
    }, {once: true});
    actions.append(accept);

    resolveResult = resolve;
    dialog.showModal();
    if (options.prompt) input.focus();
    else (options.confirm ? actions.firstElementChild : accept).focus();
  }

  function open(text, options = {}) {
    return new Promise(resolve => {
      queue.push({text, options, resolve});
      openNext();
    });
  }

  dialog.addEventListener('cancel', event => {
    event.preventDefault();
    close(activePrompt ? null : false);
  });
  dialog.addEventListener('click', event => {
    if (event.target === dialog) close(activePrompt ? null : false);
  });

  window.appModal = {
    show: (text, options) => open(text, options),
    confirm: (text, options = {}) => open(text, {...options, confirm: true}),
    prompt: (text, options = {}) => open(text, {...options, prompt: true})
  };
})();
