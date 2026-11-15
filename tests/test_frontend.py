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
const calls = [];
let testUsers = [{id:2, usuario:'func-teste', perfil:'funcionario'}];
let confirmDeletion = true;
window.confirm = () => confirmDeletion;
const testOrder = {id:42, cliente:'Cliente', criado_em:'01/01/2026 10:00', telefone:'12345678',
  status:'Recebido', total:10, forma_pagamento:'Pix', observacao:'',
  itens:[{nome_produto:'Bolo', quantidade:1, subtotal:10}]};
window.fetch = async (path, opts={}) => {
  await Promise.resolve();
  calls.push([path, opts.method || 'GET', opts.body]);
  let data = {ok: true};
  if (path === '/api/dashboard') data = {espera:0, ativos:0, atendidos:0,
    faturamento:testOrder.status === 'Concluído' ? testOrder.total : 0};
  else if (path === '/api/categorias') data = [{id:1, nome:'Bolos', emoji:'🍰'}];
  else if (path === '/api/produtos' && (!opts.method || opts.method === 'GET')) data = [product];
  else if (path === '/api/pedidos' && opts.method === 'POST') data = {pedido_id:42, total:10};
  else if (path === '/api/meus-pedidos' && opts.method === 'POST') {
    const customer = JSON.parse(opts.body);
    data = customer.cliente === 'Cliente' && customer.telefone === '(32) 99999-9999' ? [testOrder] : [];
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
      confirmDeletion = false;
      $('tabela-usuarios').querySelectorAll('button')[1].click();
      await wait();
      check(!calls.some(([path, method]) => path === '/api/usuarios/2' && method === 'DELETE'), 'Exclusão cancelada foi enviada');
      confirmDeletion = true;
      $('tabela-usuarios').querySelectorAll('button')[1].click();
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
    } else {
      document.querySelector('.product-bottom button').click();
      $('cliente').value = 'Cliente'; $('telefone').value = '12345678';
      $('forma-pagamento').value = 'Pix';
      $('form-pedido').requestSubmit();
      await wait();
      check($('mensagem-pedido').textContent.includes('Pedido #42 registrado com sucesso'), $('mensagem-pedido').textContent);
      check($('cliente').value === '' && $('contador').textContent === '0', 'Pedido não foi limpo');
      $('historico-nome').value = 'Cliente';
      $('historico-telefone').value = '(32) 99999-9999';
      $('form-historico').requestSubmit();
      await wait();
      check($('historico-mensagem').textContent.includes('1 pedido'), $('historico-mensagem').textContent);
      check($('lista-meus-pedidos').textContent.includes('Pedido #42') &&
        $('lista-meus-pedidos').textContent.includes('Bolo'), 'Histórico de pedidos não foi exibido');
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
