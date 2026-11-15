"""Testes de interface com Chrome ou Edge, sem acesso ao banco da aplicação."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import unittest

from flask import Flask, render_template
from werkzeug.serving import make_server


ROOT = Path(__file__).resolve().parents[1]
BROWSERS = [
    os.getenv('BROWSER_PATH', ''),
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
BROWSER = next((path for path in BROWSERS if path and Path(path).is_file()), None)

MOCK_AND_TEST = r"""
<script>
const product = {id: 1, nome: 'Bolo', categoria_id: 1, categoria: 'Bolos',
  categoria_emoji: '🍰', preco: 10, custo: 4, emoji: '🍰', descricao: '',
  disponivel: true, imagens: []};
const intervals = new Map();
let nextInterval = 0;
if (location.pathname === '/') {
  product.imagens = [11, 12, 13];
  window.setInterval = (callback, delay) => {
    const id = ++nextInterval;
    intervals.set(id, {callback, delay});
    return id;
  };
  window.clearInterval = id => intervals.delete(id);
}
const calls = [];
let testUsers = [{id:2, usuario:'func-teste', perfil:'funcionario'}];
const testOrder = {id:42, cliente:'Cliente', criado_em:'01/01/2026 10:00', telefone:'12345678',
  status:'Recebido', total:10, forma_pagamento:'Pix', observacao:'',
  itens:[{nome_produto:'Bolo', quantidade:1, subtotal:10}]};
const secondTestOrder = {...testOrder, id:43, criado_em:'02/01/2026 10:00'};
window.fetch = async (path, opts={}) => {
  await Promise.resolve();
  calls.push([path, opts.method || 'GET', opts.body]);
  let data = {ok: true};
  if (path === '/api/dashboard') data = {espera:0, ativos:0, atendidos:0,
    faturamento:testOrder.status === 'Concluído' ? testOrder.total : 0};
  else if (path === '/api/categorias') data = [{id:1, nome:'Bolos', emoji:'🍰'}];
  else if (path === '/api/produtos' && (!opts.method || opts.method === 'GET')) {
    data = location.pathname === '/' ? [product,
      {...product, id:2, nome:'Uma imagem', imagens:[21]},
      {...product, id:3, nome:'Sem imagem', imagens:[]}] : [product];
  }
  else if (path === '/api/pedidos' && opts.method === 'POST') data = {pedido_id:42, total:10};
  else if (path === '/api/meus-pedidos' && opts.method === 'POST') {
    const customer = JSON.parse(opts.body);
    data = customer.cliente === 'Cliente' && customer.telefone === '(32) 99999-9999'
      ? [testOrder, secondTestOrder] : [];
  }
  else if (path === '/api/cancelar-pedido' && opts.method === 'POST') {
    const codigo = Number(JSON.parse(opts.body).codigo);
    [testOrder, secondTestOrder].find(order => order.id === codigo).status = 'Cancelado';
  }
  else if (path === '/api/cancelar-todos-pedidos' && opts.method === 'POST') {
    const request = JSON.parse(opts.body);
    const pedidos = [testOrder, secondTestOrder].filter(order => request.codigos.includes(String(order.id)));
    data = {cancelados:pedidos.filter(order => order.status === 'Recebido').map(order => order.id),
      nao_cancelados:pedidos.filter(order => order.status !== 'Recebido').map(order => order.id)};
    pedidos.forEach(order => {if (data.cancelados.includes(order.id)) order.status = 'Cancelado';});
  }
  else if (path === '/api/pedidos' && opts.method === 'GET') data = [testOrder];
  else if (path === '/api/pedidos/42/status' && opts.method === 'PATCH') testOrder.status = JSON.parse(opts.body).status;
  else if (path === '/api/usuarios' && opts.method === 'GET') data = testUsers;
  else if (path === '/api/usuarios' && opts.method === 'POST') {
    testUsers.push({id:3, ...JSON.parse(opts.body)});
  } else if (path === '/api/usuarios/2' && opts.method === 'PUT') {
    testUsers[0] = {id:2, ...JSON.parse(opts.body)}; data = {ok:true, perfil_atual:'admin'};
  } else if (path === '/api/usuarios/2' && opts.method === 'DELETE') {
    testUsers = testUsers.filter(user => user.id !== 2);
  }
  return {ok:true, json:async () => data};
};
window.addEventListener('load', async () => {
  const wait = () => new Promise(resolve => setTimeout(resolve, 50));
  const check = (condition, message) => {if (!condition) throw new Error(message);};
  const $ = id => document.getElementById(id);
  try {
    await wait();
    if ($('form-usuario')) {
      document.querySelector('[data-tab="produtos"]').click();
      await wait();
      $('novo-produto').click();
      const dialog = $('modal-produto');
      check(dialog.open, 'Modal de cadastro não abriu');
      const rect = dialog.getBoundingClientRect();
      check(Math.abs(rect.left + rect.width/2 - document.documentElement.clientWidth/2) < 2, 'Modal fora do centro horizontal');
      check(Math.abs(rect.top + rect.height/2 - document.documentElement.clientHeight/2) < 2, 'Modal fora do centro vertical');
      $('nome').value = 'Novo bolo'; $('preco').value = '10'; $('custo').value = '4';
      $('form-produto').requestSubmit();
      await wait();
      check(!dialog.open && calls.some(([path, method]) => path === '/api/produtos' && method === 'POST'), 'Cadastro não foi salvo');
      $('novo-produto').click();
      $('cancelar-edicao').click();
      check(!dialog.open, 'Cancelar não fechou o modal');
      $('tabela-produtos').querySelector('button').click();
      check(dialog.open && $('nome').value === 'Bolo', 'Edição não abriu com os dados');
      $('form-produto').requestSubmit();
      await wait();
      check(!dialog.open && calls.some(([path, method]) => path === '/api/produtos/1' && method === 'PUT'), 'Edição não foi salva');
      document.querySelector('[data-tab="usuarios"]').click();
      await wait();
      check($('tabela-usuarios').textContent.includes('func-teste'), 'Lista de usuários não carregou');
      $('usuario').value = 'usuario-teste'; $('senha').value = 'senha123';
      $('form-usuario').requestSubmit();
      await wait();
      check($('usuario-mensagem').textContent === 'Usuário cadastrado.', $('usuario-mensagem').textContent);
      check($('usuario').value === '', 'Formulário de usuário não foi limpo');
      $('tabela-usuarios').querySelector('button').click();
      check($('usuario').value === 'func-teste' && !$('senha').required, 'Edição de usuário não carregou');
      $('usuario').value = 'func-alterado';
      $('form-usuario').requestSubmit();
      await wait();
      const update = calls.find(([path, method]) => path === '/api/usuarios/2' && method === 'PUT');
      check(update && JSON.parse(update[2]).senha === '', 'Senha não foi preservada na edição');
      check($('tabela-usuarios').textContent.includes('func-alterado'), 'Lista não foi atualizada');
      $('tabela-usuarios').querySelector('button').click();
      $('tabela-usuarios').querySelectorAll('button')[1].click();
      await wait();
      const confirmation = document.querySelector('.feedback-modal');
      check(confirmation.open && confirmation.dataset.type === 'warning', 'Confirmação de exclusão não apareceu');
      confirmation.querySelector('[data-modal-cancel]').click();
      await wait();
      check(!calls.some(([path, method]) => path === '/api/usuarios/2' && method === 'DELETE'), 'Exclusão cancelada foi enviada');
      $('tabela-usuarios').querySelectorAll('button')[1].click();
      await wait();
      document.querySelector('.feedback-modal').querySelector('[data-modal-accept]').click();
      await wait();
      check(calls.some(([path, method]) => path === '/api/usuarios/2' && method === 'DELETE'), 'Exclusão não foi enviada');
      check(!$('tabela-usuarios').textContent.includes('func-alterado') && !$('usuario-id').value, 'Lista ou formulário não foi atualizado');
      document.querySelector('[data-tab="pedidos"]').click();
      await wait();
      const status = $('lista-pedidos').querySelector('select');
      status.value = 'Concluído'; status.dispatchEvent(new Event('change', {bubbles:true}));
      await wait();
      check($('total-faturamento').textContent.includes('10,00'), 'Faturamento não atualizou ao concluir pedido');
    } else if ($('form-login')) {
      const password = $('login-senha'), toggle = $('alternar-senha');
      password.value = 'senha123';
      check(password.type === 'password', 'Senha deve iniciar oculta');
      toggle.click();
      check(password.type === 'text' && password.value === 'senha123' && toggle.getAttribute('aria-pressed') === 'true'
        && toggle.getAttribute('aria-label') === 'Ocultar senha', 'Senha não ficou visível');
      toggle.click();
      check(password.type === 'password' && password.value === 'senha123' && toggle.getAttribute('aria-pressed') === 'false'
        && toggle.getAttribute('aria-label') === 'Mostrar senha' && !calls.length, 'Senha não voltou a ficar oculta');
      const pending = window.appModal.show('Erro de teste');
      await wait();
      const feedback = document.querySelector('.feedback-modal');
      const rect = feedback.getBoundingClientRect();
      check(feedback.open && feedback.dataset.type === 'error' && $('feedback-modal-message').textContent === 'Erro de teste'
        && Math.abs(rect.left + rect.width/2 - document.documentElement.clientWidth/2) < 2
        && Math.abs(rect.top + rect.height/2 - document.documentElement.clientHeight/2) < 2,
        'Modal de erro não apareceu centralizado');
      feedback.querySelector('[data-modal-accept]').click();
      await pending;
    } else {
      const cards = document.querySelectorAll('.product');
      const image = cards[0].querySelector('img');
      const currentImage = () => image.getAttribute('src');
      check(currentImage() === '/api/imagens/11' && intervals.size === 1,
        'Carrossel inicial incorreto');
      check(cards[1].querySelector('img').getAttribute('src') === '/api/imagens/21' &&
        !cards[1].querySelector('.image-controls') && !cards[2].querySelector('img') &&
        cards[2].querySelector('.product-art').textContent === '🍰', 'Produtos sem carrossel incorretos');
      let timer = [...intervals.values()][0];
      check(timer.delay === 3000, 'Intervalo do carrossel incorreto');
      timer.callback();
      check(currentImage() === '/api/imagens/12', 'Carrossel não avançou');
      timer.callback(); timer.callback();
      check(currentImage() === '/api/imagens/11', 'Carrossel não reiniciou');
      cards[0].querySelector('[aria-label="Imagem anterior"]').click();
      check(currentImage() === '/api/imagens/13' && intervals.size === 1 &&
        [...intervals.values()][0] !== timer && [...intervals.values()][0].delay === 3000,
        'Controle manual não reiniciou o temporizador');
      [...intervals.values()][0].callback();
      check(currentImage() === '/api/imagens/11', 'Carrossel não avançou após controle manual');
      $('busca').value = 'Uma imagem';
      $('busca').dispatchEvent(new Event('input'));
      check(intervals.size === 0, 'Temporizador não foi removido ao filtrar');
      $('busca').value = '';
      $('busca').dispatchEvent(new Event('input'));
      check(intervals.size === 1, 'Carrossel não foi recriado ao limpar filtro');
      document.querySelector('.product-bottom button').click();
      $('cliente').value = 'Cliente'; $('telefone').value = '12345678';
      $('forma-pagamento').value = 'Pix';
      $('form-pedido').requestSubmit();
      await wait();
      check($('mensagem-pedido').textContent.includes('Pedido registrado com sucesso') &&
        !$('mensagem-pedido').textContent.includes('#42'), $('mensagem-pedido').textContent);
      const feedback = document.querySelector('.feedback-modal');
      check(feedback.open && feedback.dataset.type === 'success', 'Confirmação do pedido não apareceu');
      check(!$('feedback-modal-message').textContent.includes('#42') &&
        $('feedback-modal-message').textContent.includes('Meus pedidos') &&
        $('feedback-modal-message').textContent.includes('cancelar'),
        'A confirmação não orientou onde consultar o ID para cancelamento');
      const feedbackRect = feedback.getBoundingClientRect();
      check(Math.abs(feedbackRect.left + feedbackRect.width/2 - document.documentElement.clientWidth/2) < 2 &&
        Math.abs(feedbackRect.top + feedbackRect.height/2 - document.documentElement.clientHeight/2) < 2,
        'Modal de feedback fora do centro');
      feedback.querySelector('[data-modal-accept]').click();
      check($('cliente').value === '' && $('contador').textContent === '0', 'Pedido não foi limpo');
      $('historico-nome').value = 'Cliente';
      $('historico-telefone').value = '(32) 99999-9999';
      $('form-historico').requestSubmit();
      await wait();
      check($('historico-mensagem').textContent.includes('2 pedido'), $('historico-mensagem').textContent);
      check($('lista-meus-pedidos').textContent.includes('Pedido #42') &&
        $('lista-meus-pedidos').textContent.includes('Pedido #43') &&
        $('lista-meus-pedidos').textContent.includes('Bolo'), 'Histórico de pedidos não foi exibido');
      $('lista-meus-pedidos').querySelector('.order-cancel').click();
      await wait();
      const cancelConfirmation = document.querySelector('.feedback-modal');
      check(cancelConfirmation.open && cancelConfirmation.dataset.type === 'warning' &&
        $('feedback-modal-message').textContent.includes('Digite o ID do pedido') &&
        !$('feedback-modal-input').classList.contains('hidden') &&
        $('feedback-modal-input-label').textContent === 'ID do pedido' &&
        $('feedback-modal-input').placeholder === 'Digite o ID do pedido',
        'Modal para digitar o ID não apareceu');
      $('feedback-modal-input').value = '999';
      cancelConfirmation.querySelector('[data-modal-accept]').click();
      await wait();
      check(!calls.some(([path]) => path === '/api/cancelar-pedido'), 'ID incorreto foi enviado para a API');
      check($('feedback-modal-message').textContent.includes('não corresponde'),
        `Erro de código inválido não apareceu: ${$('feedback-modal-message').textContent}`);
      document.querySelector('.feedback-modal').querySelector('[data-modal-accept]').click();
      await wait();
      $('lista-meus-pedidos').querySelector('.order-cancel').click();
      await wait();
      $('feedback-modal-input').value = '42';
      document.querySelector('.feedback-modal').querySelector('[data-modal-accept]').click();
      await wait();
      const cancellation = calls.find(([path, method]) => path === '/api/cancelar-pedido' && method === 'POST');
      check(cancellation && JSON.parse(cancellation[2]).codigo === '42' &&
        JSON.parse(cancellation[2]).telefone === '(32) 99999-9999',
        `Código ou telefone não foram enviados para cancelar: ${JSON.stringify(cancellation)}`);
      const cancelled = document.querySelector('.feedback-modal');
      check(cancelled.open && cancelled.dataset.type === 'success' &&
        $('lista-meus-pedidos').querySelector('[data-order-id="42"] .order-status').textContent === 'Cancelado' &&
        !$('lista-meus-pedidos').querySelector('[data-order-id="42"] .order-cancel'),
        'Cancelamento individual não foi confirmado na lista');
      cancelled.querySelector('[data-modal-accept]').click();
      const cancelAll = $('cancelar-todos-pedidos');
      check(!cancelAll.classList.contains('hidden') && cancelAll.textContent.includes('(1)'),
        'Ação para cancelar todos os pedidos restantes não apareceu');
      cancelAll.click();
      await wait();
      const cancelAllConfirmation = document.querySelector('.feedback-modal');
      check(cancelAllConfirmation.open && $('feedback-modal-message').textContent.includes('IDs dos pedidos') &&
        $('feedback-modal-input').placeholder === 'IDs separados por vírgula',
        `Modal para digitar os IDs de cancelamento não apareceu: ${$('feedback-modal-message').textContent} / ${$('feedback-modal-input').placeholder}`);
      $('feedback-modal-input').value = '43';
      cancelAllConfirmation.querySelector('[data-modal-accept]').click();
      await wait();
      const cancelAllRequest = calls.find(([path, method]) => path === '/api/cancelar-todos-pedidos' && method === 'POST');
      check(cancelAllRequest && JSON.parse(cancelAllRequest[2]).cliente === 'Cliente' &&
        JSON.parse(cancelAllRequest[2]).telefone === '(32) 99999-9999' &&
        JSON.stringify(JSON.parse(cancelAllRequest[2]).codigos) === '["43"]' &&
        $('lista-meus-pedidos').querySelector('[data-order-id="43"] .order-status').textContent === 'Cancelado' &&
        $('cancelar-todos-pedidos').classList.contains('hidden'), 'Cancelamento de todos não foi aplicado');
      document.querySelector('.feedback-modal').querySelector('[data-modal-accept]').click();
    }
    document.body.dataset.testResult = 'OK';
  } catch (error) {
    document.body.dataset.testResult = 'ERRO: ' + error.message;
  }
});
</script>
"""


@unittest.skipUnless(BROWSER, 'Chrome ou Edge não encontrado; defina BROWSER_PATH.')
class FrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Flask(__name__, root_path=str(ROOT))

        @fixture.get('/')
        def public_page():
            return render_template('index.html').replace('</body>', MOCK_AND_TEST + '</body>')

        @fixture.get('/admin')
        def admin_page():
            return render_template('admin.html', csrf='teste', perfil='admin').replace(
                '</body>', MOCK_AND_TEST + '</body>')

        @fixture.get('/login')
        def login_page():
            return render_template('login.html').replace('</body>', MOCK_AND_TEST + '</body>')

        cls.server = make_server('127.0.0.1', 0, fixture)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def check_page(self, path):
        with tempfile.TemporaryDirectory(prefix='cardapio-browser-') as profile:
            result = subprocess.run(
                [BROWSER, '--headless', '--disable-gpu', '--no-first-run',
                 f'--user-data-dir={profile}', '--virtual-time-budget=5000', '--dump-dom',
                 f'http://127.0.0.1:{self.server.server_port}{path}'],
                capture_output=True, timeout=30, check=True)
        html = result.stdout.decode('utf-8', errors='replace')
        marker = re.search(r'data-test-result="([^"]*)"', html)
        self.assertIsNotNone(marker, 'O teste não terminou no navegador.')
        self.assertEqual(marker.group(1), 'OK')

    def test_customer_order(self):
        self.check_page('/')

    def test_admin_modal_and_user_creation(self):
        self.check_page('/admin')

    def test_login_password_visibility(self):
        self.check_page('/login')


if __name__ == '__main__':
    unittest.main()
