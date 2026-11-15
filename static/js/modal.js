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
      <div class="feedback-modal-actions"></div>
    </div>`;
  document.body.append(dialog);

  const title = dialog.querySelector('#feedback-modal-title');
  const message = dialog.querySelector('#feedback-modal-message');
  const icon = dialog.querySelector('.feedback-modal-icon');
  const actions = dialog.querySelector('.feedback-modal-actions');
  const queue = [];
  let resolveResult;

  function close(result) {
    if (!dialog.open) return;
    dialog.close();
    if (resolveResult) resolveResult(result);
    resolveResult = null;
    setTimeout(openNext, 0);
  }

  function openNext() {
    if (dialog.open || !queue.length) return;
    const {text, options, resolve} = queue.shift();
    const type = options.type || 'error';
    dialog.dataset.type = type;
    dialog.setAttribute('role', options.confirm ? 'alertdialog' : 'dialog');
    title.textContent = options.title || (type === 'success' ? 'Tudo certo!' : type === 'warning' ? 'Atenção' : 'Não foi possível concluir');
    message.textContent = text;
    icon.textContent = type === 'success' ? '✓' : type === 'warning' ? '!' : '×';
    actions.replaceChildren();

    if (options.confirm) {
      const cancel = document.createElement('button');
      cancel.className = 'btn subtle';
      cancel.type = 'button';
      cancel.dataset.modalCancel = '';
      cancel.textContent = 'Cancelar';
      cancel.addEventListener('click', () => close(false), {once: true});
      actions.append(cancel);
    }

    const accept = document.createElement('button');
    accept.className = 'btn primary';
    accept.type = 'button';
    accept.dataset.modalAccept = '';
    accept.textContent = options.confirm ? (options.confirmLabel || 'Confirmar') : 'Entendi';
    accept.addEventListener('click', () => close(options.confirm ? true : undefined), {once: true});
    actions.append(accept);

    resolveResult = resolve;
    dialog.showModal();
    (options.confirm ? actions.firstElementChild : accept).focus();
  }

  function open(text, options = {}) {
    return new Promise(resolve => {
      queue.push({text, options, resolve});
      openNext();
    });
  }

  dialog.addEventListener('cancel', event => {
    event.preventDefault();
    close(false);
  });
  dialog.addEventListener('click', event => {
    if (event.target === dialog) close(false);
  });

  window.appModal = {
    show: (text, options) => open(text, options),
    confirm: (text, options = {}) => open(text, {...options, confirm: true})
  };
})();
