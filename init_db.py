"""Instala o banco e cria o administrador inicial. Execute: python init_db.py"""
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv(Path(__file__).with_name('.env'))


def main():
    config = dict(host=os.getenv('MYSQL_HOST', '127.0.0.1'),
                  port=int(os.getenv('MYSQL_PORT', '3306')),
                  user=os.getenv('MYSQL_USER', 'root'),
                  password=os.getenv('MYSQL_PASSWORD', ''),
                  charset='utf8mb4', autocommit=False)
    db_name = os.getenv('MYSQL_DATABASE', 'doceria_online')
    if not db_name.replace('_', '').isalnum():
        raise ValueError('MYSQL_DATABASE deve conter apenas letras, números ou _.')
    connection = pymysql.connect(**config)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            cursor.execute(f'USE `{db_name}`')
            # Atualiza bancos existentes antes de executar os dados iniciais.
            cursor.execute("SHOW TABLES")
            tables = {row[0] for row in cursor.fetchall()}
            migrations = {
                'categorias': [('emoji', "VARCHAR(20) NOT NULL DEFAULT '🍬'")],
                'produtos': [('custo', 'DECIMAL(10,2) NULL')],
                'administradores': [('perfil', "ENUM('admin','funcionario') NOT NULL DEFAULT 'admin'")],
                'pedidos': [('forma_pagamento', 'VARCHAR(30) NULL')],
                'itens_pedido': [('custo_unitario', 'DECIMAL(10,2) NULL')],
            }
            for table, columns in migrations.items():
                if table not in tables:
                    continue
                cursor.execute(f'SHOW COLUMNS FROM `{table}`')
                existing = {row[0] for row in cursor.fetchall()}
                for column, definition in columns:
                    if column not in existing:
                        cursor.execute(f'ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}')
                        if table == 'categorias' and column == 'emoji':
                            cursor.execute("""UPDATE categorias SET emoji=CASE nome
                                WHEN 'Bolos' THEN '🍰' WHEN 'Brigadeiros' THEN '🍫'
                                WHEN 'Tortas' THEN '🥧' WHEN 'Bebidas' THEN '☕'
                                ELSE '🍬' END""")
            sql = Path(__file__).parent.joinpath('sql/banco.sql').read_text(encoding='utf-8')
            # O arquivo usa instruções simples, sem procedimentos armazenados.
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for statement in statements:
                if statement.upper().startswith('CREATE DATABASE') or statement.upper().startswith('USE '):
                    continue
                cursor.execute(statement)
            username = os.getenv('ADMIN_USERNAME', 'admin').strip()
            password = os.getenv('ADMIN_PASSWORD', 'Admin@12345')
            if not username or not password:
                raise ValueError('Defina ADMIN_USERNAME e ADMIN_PASSWORD no .env')
            cursor.execute('SELECT id FROM administradores WHERE usuario=%s', (username,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO administradores (usuario,senha_hash) VALUES (%s,%s)',
                               (username, generate_password_hash(password)))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    print('Banco configurado! Acesse http://127.0.0.1:5000')
    print('Administrador:', username)
    print('Altere ADMIN_PASSWORD e configure uma senha segura antes da primeira instalação.')


if __name__ == '__main__':
    main()
