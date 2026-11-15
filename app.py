"""Doceria Online: Flask + MySQL (XAMPP) + HTML/CSS/JavaScript."""
import os
import re
import secrets
import base64
import binascii
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for
from pymysql.cursors import DictCursor
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv(Path(__file__).with_name('.env'))
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-only-change-me')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
app.config['MAX_CONTENT_LENGTH'] = 9 * 1024 * 1024
STATUSES = ('Recebido', 'Preparando', 'Concluído', 'Cancelado')
PAYMENTS = ('Dinheiro', 'Pix', 'Cartão de Crédito', 'Cartão de Débito')


def connect():
    return pymysql.connect(host=os.getenv('MYSQL_HOST', '127.0.0.1'),
                           port=int(os.getenv('MYSQL_PORT', '3306')),
                           user=os.getenv('MYSQL_USER', 'root'),
                           password=os.getenv('MYSQL_PASSWORD', ''),
                           database=os.getenv('MYSQL_DATABASE', 'doceria_online'),
                           charset='utf8mb4', cursorclass=DictCursor, autocommit=False)


def json_error(message, status=400):
    return jsonify({'erro': message}), status


def refresh_user(cursor):
    user_id = session.get('admin_id')
    if not user_id:
        return False
    cursor.execute('SELECT perfil FROM administradores WHERE id=%s', (user_id,))
    user = cursor.fetchone()
    if not user:
        session.clear()
        return False
    session['perfil'] = user['perfil']
    return True


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        authenticated = False
        if session.get('admin_id'):
            db = connect()
            try:
                with db.cursor() as cursor:
                    authenticated = refresh_user(cursor)
            finally:
                db.close()
        if not authenticated:
            if request.path.startswith('/api/'):
                return json_error('Faça login como administrador.', 401)
            return redirect(url_for('login'))
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            token = request.headers.get('X-CSRF-Token', '')
            if not token or not secrets.compare_digest(token, session.get('csrf', '')):
                return json_error('Token de segurança inválido. Recarregue a página.', 403)
        return view(*args, **kwargs)
    return wrapper


def manager_required(view):
    @admin_required
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get('perfil') != 'admin':
            return json_error('Acesso permitido somente ao administrador.', 403)
        return view(*args, **kwargs)
    return wrapper


def clean_product(data):
    nome = str(data.get('nome', '')).strip()
    descricao = str(data.get('descricao', '')).strip()
    emoji = str(data.get('emoji', '🍬')).strip() or '🍬'
    try:
        categoria_id = int(data.get('categoria_id'))
        preco = Decimal(str(data.get('preco', ''))).quantize(Decimal('.01'))
        custo = Decimal(str(data.get('custo', ''))).quantize(Decimal('.01'))
    except (ValueError, TypeError, InvalidOperation):
        raise ValueError('Categoria e preço devem ser válidos.')
    if not 1 <= len(nome) <= 120 or len(descricao) > 350 or len(emoji) > 20:
        raise ValueError('Confira o nome, descrição e emoji.')
    if not preco.is_finite() or not Decimal('0.01') <= preco <= Decimal('99999999.99'):
        raise ValueError('Informe preço entre R$ 0,01 e R$ 99.999.999,99.')
    if not custo.is_finite() or not Decimal('0') <= custo <= Decimal('99999999.99'):
        raise ValueError('Informe um custo entre R$ 0,00 e R$ 99.999.999,99.')
    disponivel = 1 if data.get('disponivel') is True else 0
    return categoria_id, nome, descricao, preco, custo, emoji, disponivel


def clean_images(images):
    if not isinstance(images, list) or len(images) > 3:
        raise ValueError('Selecione no máximo 3 imagens.')
    result = []
    for image in images:
        if isinstance(image, int) and not isinstance(image, bool) and image > 0:
            result.append(image)
            continue
        if not isinstance(image, str) or ',' not in image:
            raise ValueError('Imagem inválida.')
        header, encoded = image.split(',', 1)
        formats = {'data:image/png;base64': ('image/png', b'\x89PNG\r\n\x1a\n'),
                   'data:image/jpeg;base64': ('image/jpeg', b'\xff\xd8\xff'),
                   'data:image/gif;base64': ('image/gif', b'GIF8')}
        if header not in formats or len(encoded) > 2800000:
            raise ValueError('Use imagens PNG, JPEG ou GIF de até 2 MB.')
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('Imagem inválida.')
        mime, signature = formats[header]
        if not content.startswith(signature) or len(content) > 2 * 1024 * 1024:
            raise ValueError('Use imagens PNG, JPEG ou GIF de até 2 MB.')
        result.append((mime, content))
    ids = [image for image in result if isinstance(image, int)]
    if len(set(ids)) != len(ids):
        raise ValueError('Imagens repetidas.')
    return result


def save_images(cursor, product_id, images):
    cursor.execute('SELECT id FROM imagens_produto WHERE produto_id=%s', (product_id,))
    existing = {row['id'] for row in cursor.fetchall()}
    retained = {image for image in images if isinstance(image, int)}
    if not retained.issubset(existing):
        raise ValueError('Imagem não pertence a este produto.')
    for image_id in existing - retained:
        cursor.execute('DELETE FROM imagens_produto WHERE id=%s AND produto_id=%s', (image_id, product_id))
    for image in images:
        if isinstance(image, tuple):
            cursor.execute('INSERT INTO imagens_produto (produto_id,tipo,dados) VALUES (%s,%s,%s)',
                           (product_id, image[0], image[1]))


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/login')
def login():
    if session.get('admin_id'):
        return redirect(url_for('admin'))
    return render_template('login.html')


@app.post('/api/login')
def api_login():
    data = request.get_json(silent=True) or {}
    usuario = str(data.get('usuario', ''))[:80]
    senha = str(data.get('senha', ''))
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT id, senha_hash, perfil FROM administradores WHERE usuario=%s', (usuario,))
            admin_user = cursor.fetchone()
    finally:
        db.close()
    if not admin_user or not check_password_hash(admin_user['senha_hash'], senha):
        return json_error('Usuário ou senha incorretos.', 401)
    session.clear()
    session['admin_id'] = admin_user['id']
    session['perfil'] = admin_user['perfil']
    session['csrf'] = secrets.token_urlsafe(32)
    return jsonify({'ok': True, 'redirecionar': '/admin'})


@app.get('/admin')
@admin_required
def admin():
    return render_template('admin.html', csrf=session['csrf'], perfil=session.get('perfil'))


@app.post('/api/logout')
@admin_required
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.get('/api/categorias')
def categorias():
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT id, nome, emoji FROM categorias ORDER BY nome')
            return jsonify(cursor.fetchall())
    finally:
        db.close()


@app.get('/api/produtos')
def produtos():
    db = connect()
    try:
        with db.cursor() as cursor:
            publico = not refresh_user(cursor)
            cursor.execute('''SELECT p.id, p.nome, p.descricao, p.preco, p.custo, p.emoji,
                              p.disponivel, p.categoria_id, c.nome AS categoria, c.emoji AS categoria_emoji
                              FROM produtos p JOIN categorias c ON p.categoria_id=c.id
                              ''' + ('WHERE p.disponivel=1 ' if publico else '') + 'ORDER BY c.nome, p.nome')
            rows = cursor.fetchall()
            for row in rows:
                row['preco'] = float(row['preco'])
                if session.get('perfil') == 'admin':
                    row['custo'] = float(row['custo']) if row['custo'] is not None else None
                else:
                    del row['custo']
                cursor.execute('SELECT id FROM imagens_produto WHERE produto_id=%s ORDER BY id', (row['id'],))
                row['imagens'] = [image['id'] for image in cursor.fetchall()]
            return jsonify(rows)
    finally:
        db.close()


@app.post('/api/produtos')
@manager_required
def criar_produto():
    try:
        body = request.get_json(silent=True) or {}
        data = clean_product(body)
        images = clean_images(body.get('imagens', []))
        if any(isinstance(image, int) for image in images):
            raise ValueError('Imagens existentes não podem ser usadas em um novo produto.')
    except ValueError as exc:
        return json_error(str(exc))
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT id FROM categorias WHERE id=%s', (data[0],))
            if not cursor.fetchone():
                return json_error('Categoria não encontrada.')
            cursor.execute('''INSERT INTO produtos
                (categoria_id,nome,descricao,preco,custo,emoji,disponivel) VALUES (%s,%s,%s,%s,%s,%s,%s)''', data)
            product_id = cursor.lastrowid
            save_images(cursor, product_id, images)
        db.commit()
        return jsonify({'id': product_id, 'ok': True}), 201
    finally:
        db.close()


@app.put('/api/produtos/<int:product_id>')
@manager_required
def editar_produto(product_id):
    try:
        body = request.get_json(silent=True) or {}
        data = clean_product(body)
        images = clean_images(body.get('imagens', []))
    except ValueError as exc:
        return json_error(str(exc))
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT id FROM produtos WHERE id=%s FOR UPDATE', (product_id,))
            if not cursor.fetchone():
                return json_error('Produto não encontrado.', 404)
            cursor.execute('SELECT id FROM categorias WHERE id=%s', (data[0],))
            if not cursor.fetchone():
                return json_error('Categoria não encontrada.')
            cursor.execute('''UPDATE produtos SET categoria_id=%s,nome=%s,descricao=%s,
                preco=%s,custo=%s,emoji=%s,disponivel=%s WHERE id=%s''', (*data, product_id))
            try:
                save_images(cursor, product_id, images)
            except ValueError as exc:
                db.rollback()
                return json_error(str(exc))
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@app.delete('/api/produtos/<int:product_id>')
@manager_required
def remover_produto(product_id):
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('DELETE FROM produtos WHERE id=%s', (product_id,))
            if not cursor.rowcount:
                return json_error('Produto não encontrado.', 404)
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@app.get('/api/imagens/<int:image_id>')
def imagem_produto(image_id):
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT tipo,dados FROM imagens_produto WHERE id=%s', (image_id,))
            image = cursor.fetchone()
            if not image:
                return json_error('Imagem não encontrada.', 404)
            return Response(image['dados'], mimetype=image['tipo'],
                            headers={'X-Content-Type-Options': 'nosniff'})
    finally:
        db.close()


@app.post('/api/pedidos')
def fazer_pedido():
    data = request.get_json(silent=True) or {}
    cliente = str(data.get('cliente', '')).strip()
    telefone = str(data.get('telefone', '')).strip()
    observacao = str(data.get('observacao', '')).strip()
    pagamento = data.get('forma_pagamento')
    items = data.get('itens', [])
    if not 2 <= len(cliente) <= 120 or not re.fullmatch(r'[+()\d\s-]{8,30}', telefone):
        return json_error('Informe nome e telefone válidos.')
    if len(observacao) > 500 or not isinstance(items, list) or not 1 <= len(items) <= 50:
        return json_error('Pedido inválido ou observação muito longa.')
    if pagamento not in PAYMENTS:
        return json_error('Selecione uma forma de pagamento válida.')
    quantities = {}
    try:
        for item in items:
            product_id, qtd = int(item['id']), int(item['quantidade'])
            if product_id < 1 or not 1 <= qtd <= 99 or product_id in quantities:
                raise ValueError()
            quantities[product_id] = qtd
    except (ValueError, TypeError, KeyError):
        return json_error('Há itens inválidos no carrinho.')
    db = connect()
    try:
        with db.cursor() as cursor:
            keys = sorted(quantities)
            placeholders = ','.join(['%s'] * len(keys))
            cursor.execute(f'''SELECT id, nome, preco FROM produtos
                WHERE disponivel=1 AND id IN ({placeholders}) FOR UPDATE''', keys)
            products = cursor.fetchall()
            if len(products) != len(keys):
                return json_error('Algum produto não está disponível. Atualize o cardápio.')
            total = sum((p['preco'] * quantities[p['id']] for p in products), Decimal('0'))
            cursor.execute('''INSERT INTO pedidos (cliente,telefone,observacao,total,forma_pagamento)
                VALUES (%s,%s,%s,%s,%s)''', (cliente, telefone, observacao, total, pagamento))
            order_id = cursor.lastrowid
            for p in products:
                qtd = quantities[p['id']]
                cursor.execute('''INSERT INTO itens_pedido
                  (pedido_id,produto_id,nome_produto,quantidade,preco_unitario,subtotal)
                  VALUES (%s,%s,%s,%s,%s,%s)''',
                  (order_id, p['id'], p['nome'], qtd, p['preco'], p['preco'] * qtd))
        db.commit()
        return jsonify({'ok': True, 'pedido_id': order_id, 'total': float(total)}), 201
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.get('/api/pedidos')
@admin_required
def listar_pedidos():
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('''SELECT id,cliente,telefone,observacao,total,status,forma_pagamento,
                              DATE_FORMAT(criado_em, '%d/%m/%Y %H:%i') AS criado_em
                              FROM pedidos ORDER BY id DESC''')
            orders = cursor.fetchall()
            for order in orders:
                order['total'] = float(order['total'])
                cursor.execute('''SELECT nome_produto,quantidade,preco_unitario,subtotal
                                  FROM itens_pedido WHERE pedido_id=%s''', (order['id'],))
                order['itens'] = cursor.fetchall()
                for item in order['itens']:
                    item['preco_unitario'] = float(item['preco_unitario'])
                    item['subtotal'] = float(item['subtotal'])
            return jsonify(orders)
    finally:
        db.close()


@app.patch('/api/pedidos/<int:order_id>/status')
@admin_required
def alterar_status(order_id):
    status = (request.get_json(silent=True) or {}).get('status', '')
    if status not in STATUSES:
        return json_error('Status inválido.')
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('UPDATE pedidos SET status=%s WHERE id=%s', (status, order_id))
            if not cursor.rowcount:
                cursor.execute('SELECT id FROM pedidos WHERE id=%s', (order_id,))
                if not cursor.fetchone():
                    return json_error('Pedido não encontrado.', 404)
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@app.get('/api/dashboard')
@admin_required
def dashboard():
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT status, COUNT(*) AS quantidade FROM pedidos GROUP BY status')
            counts = {row['status']: row['quantidade'] for row in cursor.fetchall()}
            result = {'espera': counts.get('Recebido', 0), 'ativos': counts.get('Preparando', 0),
                      'atendidos': counts.get('Concluído', 0)}
            if session.get('perfil') == 'admin':
                cursor.execute("SELECT COALESCE(SUM(total),0) AS faturamento FROM pedidos WHERE status='Concluído'")
                totals = cursor.fetchone()
                result['faturamento'] = float(totals['faturamento'])
            return jsonify(result)
    finally:
        db.close()


@app.post('/api/usuarios')
@manager_required
def criar_usuario():
    data = request.get_json(silent=True) or {}
    usuario = str(data.get('usuario', '')).strip()
    senha = str(data.get('senha', ''))
    perfil = data.get('perfil')
    if not 3 <= len(usuario) <= 80 or not 8 <= len(senha) <= 256 or perfil not in ('admin', 'funcionario'):
        return json_error('Informe usuário (3 a 80 caracteres), senha (8 a 256) e perfil válidos.')
    db = connect()
    try:
        with db.cursor() as cursor:
            try:
                cursor.execute('INSERT INTO administradores (usuario,senha_hash,perfil) VALUES (%s,%s,%s)',
                               (usuario, generate_password_hash(senha), perfil))
            except pymysql.IntegrityError as exc:
                if exc.args[0] == 1062:
                    return json_error('Este usuário já existe.', 409)
                raise
        db.commit()
        return jsonify({'ok': True}), 201
    finally:
        db.close()


@app.get('/api/usuarios')
@manager_required
def listar_usuarios():
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT id,usuario,perfil FROM administradores ORDER BY usuario')
            return jsonify(cursor.fetchall())
    finally:
        db.close()


@app.put('/api/usuarios/<int:user_id>')
@manager_required
def editar_usuario(user_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return json_error('Dados de usuário inválidos.')
    usuario = data.get('usuario')
    senha = data.get('senha', '')
    perfil = data.get('perfil')
    if (not isinstance(usuario, str) or not 3 <= len(usuario.strip()) <= 80
            or not isinstance(senha, str) or (senha and not 8 <= len(senha) <= 256)
            or perfil not in ('admin', 'funcionario')):
        return json_error('Informe usuário (3 a 80 caracteres), senha (8 a 256, se alterada) e perfil válidos.')
    usuario = usuario.strip()
    senha_hash = generate_password_hash(senha) if senha else None
    db = connect()
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT id,perfil FROM administradores ORDER BY id FOR UPDATE')
            users = cursor.fetchall()
            target = next((user for user in users if user['id'] == user_id), None)
            if not target:
                return json_error('Usuário não encontrado.', 404)
            if target['perfil'] == 'admin' and perfil != 'admin' and sum(user['perfil'] == 'admin' for user in users) <= 1:
                return json_error('É necessário manter pelo menos um administrador.', 400)
            try:
                if senha_hash:
                    cursor.execute('UPDATE administradores SET usuario=%s,perfil=%s,senha_hash=%s WHERE id=%s',
                                   (usuario, perfil, senha_hash, user_id))
                else:
                    cursor.execute('UPDATE administradores SET usuario=%s,perfil=%s WHERE id=%s',
                                   (usuario, perfil, user_id))
            except pymysql.IntegrityError as exc:
                if exc.args[0] == 1062:
                    return json_error('Este usuário já existe.', 409)
                raise
        db.commit()
        if user_id == session.get('admin_id'):
            session['perfil'] = perfil
        return jsonify({'ok': True, 'perfil_atual': session['perfil']})
    finally:
        db.close()


@app.errorhandler(413)
def request_too_large(_error):
    return json_error('Arquivos muito grandes. Use até 3 imagens de 2 MB.', 413)


@app.errorhandler(pymysql.MySQLError)
def mysql_error(_error):
    app.logger.exception('Falha no MySQL')
    return json_error('Não foi possível acessar o banco de dados. Verifique o MySQL do XAMPP.', 503)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
