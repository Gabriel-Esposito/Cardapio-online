"""Testes de integração isolados. Execute com TEST_MYSQL=1 e MySQL disponível."""
import base64
import os
import unittest
import uuid

import pymysql

import app as site
import init_db


@unittest.skipUnless(os.getenv('TEST_MYSQL') == '1', 'Defina TEST_MYSQL=1 para testar com MySQL.')
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_database = os.environ.get('MYSQL_DATABASE')
        cls.database = 'cardapio_test_' + uuid.uuid4().hex
        os.environ['MYSQL_DATABASE'] = cls.database
        cls.server = pymysql.connect(
            host=os.getenv('MYSQL_HOST', '127.0.0.1'),
            port=int(os.getenv('MYSQL_PORT', '3306')),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            charset='utf8mb4', autocommit=True)
        try:
            with cls.server.cursor() as cursor:
                cursor.execute(f'CREATE DATABASE `{cls.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
                cursor.execute(f'USE `{cls.database}`')
                for sql in (
                    "CREATE TABLE categorias (id INT AUTO_INCREMENT PRIMARY KEY, nome VARCHAR(80) NOT NULL UNIQUE) ENGINE=InnoDB",
                    "CREATE TABLE produtos (id INT AUTO_INCREMENT PRIMARY KEY, categoria_id INT NOT NULL, nome VARCHAR(120) NOT NULL, descricao VARCHAR(350) NOT NULL DEFAULT '', preco DECIMAL(10,2) NOT NULL, emoji VARCHAR(20) NOT NULL DEFAULT '🍬', disponivel TINYINT(1) NOT NULL DEFAULT 1, criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB",
                    "CREATE TABLE administradores (id INT AUTO_INCREMENT PRIMARY KEY, usuario VARCHAR(80) NOT NULL UNIQUE, senha_hash VARCHAR(255) NOT NULL) ENGINE=InnoDB",
                    "CREATE TABLE pedidos (id INT AUTO_INCREMENT PRIMARY KEY, cliente VARCHAR(120) NOT NULL, telefone VARCHAR(30) NOT NULL, observacao VARCHAR(500) NOT NULL DEFAULT '', total DECIMAL(10,2) NOT NULL, status ENUM('Recebido','Preparando','Concluído','Cancelado') NOT NULL DEFAULT 'Recebido', criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB",
                    "CREATE TABLE itens_pedido (id INT AUTO_INCREMENT PRIMARY KEY, pedido_id INT NOT NULL, produto_id INT NULL, nome_produto VARCHAR(120) NOT NULL, quantidade INT NOT NULL, preco_unitario DECIMAL(10,2) NOT NULL, subtotal DECIMAL(10,2) NOT NULL) ENGINE=InnoDB",
                ):
                    cursor.execute(sql)
                cursor.execute("INSERT INTO categorias VALUES (1,'Bolos')")
                cursor.execute("INSERT INTO pedidos (cliente,telefone,total,status) VALUES ('Antigo','12345678',10,'Concluído')")
                cursor.execute("INSERT INTO itens_pedido (pedido_id,nome_produto,quantidade,preco_unitario,subtotal) VALUES (1,'Antigo',1,10,10)")
            init_db.main()
            init_db.main()
        except Exception:
            with cls.server.cursor() as cursor:
                cursor.execute(f'DROP DATABASE IF EXISTS `{cls.database}`')
            cls.server.close()
            cls.restore_environment()
            raise

    @classmethod
    def restore_environment(cls):
        if cls.original_database is None:
            os.environ.pop('MYSQL_DATABASE', None)
        else:
            os.environ['MYSQL_DATABASE'] = cls.original_database

    @classmethod
    def tearDownClass(cls):
        with cls.server.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{cls.database}`')
        cls.server.close()
        cls.restore_environment()

    def setUp(self):
        self.client = site.app.test_client()
        with self.client.session_transaction() as session:
            session['admin_id'] = 1
            session['perfil'] = 'admin'
            session['csrf'] = 'teste'
        self.headers = {'X-CSRF-Token': 'teste'}

    def product(self, **changes):
        data = {'nome': 'Teste', 'categoria_id': 1, 'preco': '5.00', 'custo': '2.50',
                'descricao': '', 'emoji': '🍬', 'disponivel': True, 'imagens': []}
        data.update(changes)
        return data

    def test_completed_order_revenue_and_price_snapshot(self):
        self.assertIn('Produtos', self.client.get('/admin').get_data(as_text=True))
        category = next(c for c in self.client.get('/api/categorias').json if c['id'] == 1)
        self.assertEqual(category['emoji'], '🍰')
        db = site.connect()
        try:
            with db.cursor() as cursor:
                cursor.execute('UPDATE itens_pedido SET custo_unitario=3 WHERE pedido_id=1')
            db.commit()
        finally:
            db.close()
        self.assertEqual(self.client.get('/api/dashboard').json['faturamento'], 10.0)
        response = self.client.post('/api/produtos', json=self.product(), headers=self.headers)
        self.assertEqual(response.status_code, 201)
        product_id = response.json['id']
        order = {'cliente': 'Cliente', 'telefone': '12345678', 'forma_pagamento': 'Pix',
                 'itens': [{'id': product_id, 'quantidade': 2}]}
        self.assertEqual(self.client.post('/api/pedidos', json={**order, 'forma_pagamento': 'Outro'}).status_code, 400)
        response = self.client.post('/api/pedidos', json=order)
        self.assertEqual(response.status_code, 201)
        order_id = response.json['pedido_id']
        db = site.connect()
        try:
            with db.cursor() as cursor:
                cursor.execute('SELECT preco_unitario,custo_unitario FROM itens_pedido WHERE pedido_id=%s', (order_id,))
                item = cursor.fetchone()
                self.assertEqual(float(item['preco_unitario']), 5.0)
                self.assertIsNone(item['custo_unitario'])
        finally:
            db.close()
        self.assertEqual(self.client.get('/api/dashboard').json['espera'], 1)
        self.assertEqual(self.client.get('/api/dashboard').json['faturamento'], 10.0)
        response = self.client.patch(f'/api/pedidos/{order_id}/status', json={'status': 'Preparando'}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard').json['ativos'], 1)
        response = self.client.patch(f'/api/pedidos/{order_id}/status', json={'status': 'Concluído'}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.put(f'/api/produtos/{product_id}', json=self.product(preco='99', custo='4'), headers=self.headers)
        self.assertEqual(response.status_code, 200)
        dashboard = self.client.get('/api/dashboard').json
        self.assertEqual(dashboard['faturamento'], 20.0)
        self.assertNotIn('lucro', dashboard)
        response = self.client.patch(f'/api/pedidos/{order_id}/status', json={'status': 'Cancelado'}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard').json['faturamento'], 10.0)
        response = self.client.patch(f'/api/pedidos/{order_id}/status', json={'status': 'Concluído'}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard').json['faturamento'], 20.0)
        db = site.connect()
        try:
            with db.cursor() as cursor:
                cursor.execute('SELECT custo_unitario FROM itens_pedido WHERE pedido_id=1')
                self.assertEqual(float(cursor.fetchone()['custo_unitario']), 3.0)
        finally:
            db.close()
        orders = self.client.get('/api/pedidos').json
        self.assertEqual(next(p for p in orders if p['id'] == order_id)['forma_pagamento'], 'Pix')
        self.assertIsNone(next(p for p in orders if p['id'] == 1)['forma_pagamento'])

    def test_images_and_permissions(self):
        png = 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\nexample').decode()
        self.assertEqual(self.client.post('/api/produtos', json=self.product(imagens=[png]*4), headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/produtos', json=self.product(imagens=['data:image/png;base64,YQ==']), headers=self.headers).status_code, 400)
        response = self.client.post('/api/produtos', json=self.product(imagens=[png, png, png]), headers=self.headers)
        self.assertEqual(response.status_code, 201)
        product_id = response.json['id']
        product = next(p for p in self.client.get('/api/produtos').json if p['id'] == product_id)
        self.assertEqual(len(product['imagens']), 3)
        self.assertEqual(self.client.get(f"/api/imagens/{product['imagens'][0]}").mimetype, 'image/png')
        response = self.client.put(f'/api/produtos/{product_id}', json=self.product(imagens=[]), headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f"/api/imagens/{product['imagens'][0]}").status_code, 404)
        response = self.client.post('/api/usuarios', json={'usuario': 'func-teste', 'senha': 'senha123', 'perfil': 'funcionario'}, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.client.post('/api/logout', headers=self.headers)
        response = self.client.post('/api/login', json={'usuario': 'func-teste', 'senha': 'senha123'})
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            headers = {'X-CSRF-Token': session['csrf']}
        self.assertNotIn('Cadastrar usuário', self.client.get('/admin').get_data(as_text=True))
        self.assertEqual(self.client.post('/api/produtos', json=self.product(), headers=headers).status_code, 403)
        self.assertEqual(self.client.post('/api/usuarios', json={}, headers=headers).status_code, 403)
        self.assertNotIn('faturamento', self.client.get('/api/dashboard').json)
        self.assertNotIn('custo', self.client.get('/api/produtos').json[0])
        self.assertEqual(self.client.get('/api/pedidos').status_code, 200)

    def test_user_listing_and_editing(self):
        users = self.client.get('/api/usuarios').json
        self.assertTrue(users)
        self.assertTrue(all(set(user) == {'id', 'usuario', 'perfil'} for user in users))
        admin = next(user for user in users if user['id'] == 1)
        response = self.client.put('/api/usuarios/1',
            json={'usuario': admin['usuario'], 'perfil': 'funcionario', 'senha': ''}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/usuarios',
            json={'usuario': 'editavel', 'senha': 'senha123', 'perfil': 'funcionario'}, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        user = next(user for user in self.client.get('/api/usuarios').json if user['usuario'] == 'editavel')
        url = f"/api/usuarios/{user['id']}"
        self.assertEqual(self.client.put(url, json=['inválido'], headers=self.headers).status_code, 400)
        self.assertEqual(self.client.put(url, json={'usuario': admin['usuario'], 'perfil': 'funcionario'},
                                         headers=self.headers).status_code, 409)
        self.assertEqual(self.client.put(url, json={'usuario': 'novo-nome', 'perfil': 'funcionario', 'senha': 'curta'},
                                         headers=self.headers).status_code, 400)
        self.assertEqual(self.client.put('/api/usuarios/999999', json={'usuario': 'inexistente', 'perfil': 'funcionario'},
                                         headers=self.headers).status_code, 404)
        response = self.client.put(url, json={'usuario': 'novo-nome', 'perfil': 'funcionario', 'senha': ''},
                                   headers=self.headers)
        self.assertEqual(response.status_code, 200)
        employee = site.app.test_client()
        self.assertEqual(employee.post('/api/login', json={'usuario': 'novo-nome', 'senha': 'senha123'}).status_code, 200)
        self.assertEqual(employee.get('/api/usuarios').status_code, 403)
        self.assertEqual(self.client.put(url, json={'usuario': 'novo-nome', 'perfil': 'admin'},
                                         headers=self.headers).status_code, 200)
        self.assertEqual(employee.get('/api/usuarios').status_code, 200)
        self.assertEqual(self.client.put(url, json={'usuario': 'novo-nome', 'perfil': 'funcionario', 'senha': 'nova-senha'},
                                         headers=self.headers).status_code, 200)
        self.assertEqual(employee.get('/api/usuarios').status_code, 403)
        self.assertNotIn('faturamento', employee.get('/api/dashboard').json)
        self.assertNotIn('custo', employee.get('/api/produtos').json[0])
        self.assertEqual(employee.post('/api/login', json={'usuario': 'novo-nome', 'senha': 'senha123'}).status_code, 401)
        self.assertEqual(employee.post('/api/login', json={'usuario': 'novo-nome', 'senha': 'nova-senha'}).status_code, 200)

    def test_user_deletion_and_session_invalidation(self):
        self.assertEqual(self.client.delete('/api/usuarios/1', headers=self.headers).status_code, 400)
        self.assertEqual(self.client.delete('/api/usuarios/999999', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.delete('/api/usuarios/1').status_code, 403)
        for username, role in [('excluir-func', 'funcionario'), ('excluir-admin', 'admin')]:
            response = self.client.post('/api/usuarios',
                json={'usuario': username, 'senha': 'senha123', 'perfil': role}, headers=self.headers)
            self.assertEqual(response.status_code, 201)
        users = self.client.get('/api/usuarios').json
        employee_id = next(user['id'] for user in users if user['usuario'] == 'excluir-func')
        admin_id = next(user['id'] for user in users if user['usuario'] == 'excluir-admin')
        employee = site.app.test_client()
        self.assertEqual(employee.post('/api/login', json={'usuario': 'excluir-func', 'senha': 'senha123'}).status_code, 200)
        with employee.session_transaction() as session:
            employee_headers = {'X-CSRF-Token': session['csrf']}
        self.assertEqual(employee.delete(f'/api/usuarios/{admin_id}', headers=employee_headers).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/usuarios/{employee_id}', headers=self.headers).status_code, 200)
        self.assertEqual(employee.get('/api/pedidos').status_code, 401)
        self.assertEqual(employee.post('/api/login', json={'usuario': 'excluir-func', 'senha': 'senha123'}).status_code, 401)
        other_admin = site.app.test_client()
        self.assertEqual(other_admin.post('/api/login', json={'usuario': 'excluir-admin', 'senha': 'senha123'}).status_code, 200)
        with other_admin.session_transaction() as session:
            admin_headers = {'X-CSRF-Token': session['csrf']}
        response = other_admin.delete(f'/api/usuarios/{admin_id}', headers=admin_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['redirecionar'], '/login')
        self.assertEqual(other_admin.get('/api/usuarios').status_code, 401)
        self.assertEqual(self.client.delete('/api/usuarios/1', headers=self.headers).status_code, 400)


if __name__ == '__main__':
    unittest.main()
