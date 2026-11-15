CREATE DATABASE IF NOT EXISTS doceria_online CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE doceria_online;

CREATE TABLE IF NOT EXISTS categorias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(80) NOT NULL UNIQUE,
    emoji VARCHAR(20) NOT NULL DEFAULT '🍬'
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS produtos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    categoria_id INT NOT NULL,
    nome VARCHAR(120) NOT NULL,
    descricao VARCHAR(350) NOT NULL DEFAULT '',
    preco DECIMAL(10,2) NOT NULL,
    custo DECIMAL(10,2) NULL,
    emoji VARCHAR(20) NOT NULL DEFAULT '🍬',
    disponivel TINYINT(1) NOT NULL DEFAULT 1,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_produtos_categoria FOREIGN KEY (categoria_id) REFERENCES categorias(id),
    CONSTRAINT ck_produtos_preco CHECK (preco >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS administradores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(80) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    perfil ENUM('admin','funcionario') NOT NULL DEFAULT 'admin'
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pedidos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente VARCHAR(120) NOT NULL,
    telefone VARCHAR(30) NOT NULL,
    observacao VARCHAR(500) NOT NULL DEFAULT '',
    total DECIMAL(10,2) NOT NULL,
    forma_pagamento VARCHAR(30) NULL,
    status ENUM('Recebido','Preparando','Concluído','Cancelado') NOT NULL DEFAULT 'Recebido',
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS itens_pedido (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL,
    produto_id INT NULL,
    nome_produto VARCHAR(120) NOT NULL,
    quantidade INT NOT NULL,
    preco_unitario DECIMAL(10,2) NOT NULL,
    custo_unitario DECIMAL(10,2) NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_itens_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
    CONSTRAINT fk_itens_produto FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS imagens_produto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    produto_id INT NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    dados MEDIUMBLOB NOT NULL,
    CONSTRAINT fk_imagens_produto FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

INSERT IGNORE INTO categorias (id, nome, emoji) VALUES
(1, 'Bolos', '🍰'), (2, 'Brigadeiros', '🍫'), (3, 'Tortas', '🥧'), (4, 'Bebidas', '☕');

INSERT INTO produtos (categoria_id, nome, descricao, preco, emoji) 
SELECT 1, 'Bolo de Chocolate', 'Fatia de bolo fofinho com cobertura de chocolate.', 12.90, '🍰'
WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = 'Bolo de Chocolate');
INSERT INTO produtos (categoria_id, nome, descricao, preco, emoji)
SELECT 1, 'Bolo de Morango', 'Fatia de bolo com creme e morangos frescos.', 14.50, '🍓'
WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = 'Bolo de Morango');
INSERT INTO produtos (categoria_id, nome, descricao, preco, emoji)
SELECT 2, 'Brigadeiro Gourmet', 'Brigadeiro artesanal com granulado belga.', 4.50, '🍫'
WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = 'Brigadeiro Gourmet');
INSERT INTO produtos (categoria_id, nome, descricao, preco, emoji)
SELECT 2, 'Beijinho', 'Doce de coco com acabamento delicado.', 4.00, '🥥'
WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = 'Beijinho');
INSERT INTO produtos (categoria_id, nome, descricao, preco, emoji)
SELECT 3, 'Torta de Limão', 'Torta cremosa com merengue e raspas de limão.', 13.00, '🥧'
WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = 'Torta de Limão');
INSERT INTO produtos (categoria_id, nome, descricao, preco, emoji)
SELECT 4, 'Café Cremoso', 'Café preparado na hora.', 6.00, '☕'
WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = 'Café Cremoso');
