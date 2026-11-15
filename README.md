#  Doce Encanto — Cardápio Online

Projeto acadêmico simples de uma doceria, com **HTML + CSS + JavaScript puro**, **Python (Flask)**, **MySQL (XAMPP)** e **phpMyAdmin** como interface web para administração do banco de dados.

## Funcionalidades
- Cardápio público com pesquisa por nome e filtro de categoria.
- Carrinho com alteração de quantidades, total e finalização de pedido.
- Pedidos salvos em MySQL (o total é recalculado pelo servidor).
- Login do administrador (senha criptografada com hash).
- Painel: cadastrar, editar, excluir e marcar produtos como disponíveis.
- Painel: visualizar pedidos e alterar status.
- Visual responsivo para celular e computador.
- Menu lateral com dashboard, pedidos ativos e histórico de pedidos concluídos e cancelados.
- Administradores cadastram funcionários e outros administradores; funcionários gerenciam pedidos.
- Administradores podem listar e editar usuários, incluindo nome de acesso, perfil e senha. É necessário manter pelo menos um administrador.
- Produtos podem ter até três imagens (PNG, JPEG ou GIF, até 2 MB cada); sem capa usa o emoji da categoria.
- Forma de pagamento registrada no pedido: dinheiro, Pix, cartão de crédito ou débito.
- Faturamento dos pedidos concluídos calculado pela soma dos preços registrados nos pedidos, sem descontar custos.

## Requisitos
- Windows 10/11 com **Python 3.10+** instalado e marcado como `Add Python to PATH`.
- **XAMPP** com MySQL/MariaDB iniciado. O phpMyAdmin é opcional, mas facilita o gerenciamento do banco.
- Porta **3306** disponível no XAMPP (ou altere `MYSQL_PORT` no `.env`).

## Como executar pelo PowerShell (Windows)
1. Abra o painel do XAMPP e clique **Start** em **MySQL**. Se quiser usar o phpMyAdmin, clique **Start** em **Apache** também.
2. Extraia o ZIP e abra o PowerShell dentro da pasta `doceria_online`.
3. Execute os comandos abaixo, um por linha:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

4. Abra o arquivo `.env` e ajuste **MYSQL_USER**, **MYSQL_PASSWORD**, **MYSQL_PORT** conforme o XAMPP. Troque `FLASK_SECRET_KEY` e `ADMIN_PASSWORD` por valores seguros antes da instalação.
5. Inicialize o banco, tabelas, produtos de exemplo e usuário administrador:

```powershell
python init_db.py
```

6. Inicie a aplicação:

```powershell
python app.py
```

7. Abra no navegador:
   - **Cardápio:** http://127.0.0.1:5000
   - **Painel:** http://127.0.0.1:5000/login
   - **phpMyAdmin:** http://localhost/phpmyadmin (Apache e MySQL do XAMPP ligados)

### Acesso inicial do administrador
- Usuário: `admin`
- Senha: `Admin@12345` (valor de exemplo em `.env.example`; **altere antes de executar `init_db.py`**).

> Atenção: mudar `ADMIN_PASSWORD` depois da primeira inicialização **não altera** a senha já gravada no banco. O `init_db.py` cria o administrador apenas se o usuário não existir.

### Atualização de um banco existente

Faça um backup do banco e execute novamente `python init_db.py` antes de iniciar a versão atualizada. O script adiciona as novas colunas e a tabela de imagens sem apagar pedidos ou produtos. O dashboard soma os valores dos pedidos concluídos, inclusive os antigos, sem descontar custos; esse valor é faturamento, não lucro. Custos já gravados em pedidos antigos são preservados, mas novos pedidos não registram custo.

O dashboard considera pedidos `Recebido` como em espera, `Preparando` como ativos e `Concluído` como atendidos. Cancelados aparecem no histórico. A forma de pagamento é apenas informativa; o sistema não processa pagamentos.

Para executar os testes de integração, com MySQL ativo e permissão para criar bancos temporários:

```powershell
$env:TEST_MYSQL = "1"
python -m unittest discover -s tests -v
```

Os testes criam e removem um banco isolado com nome aleatório; não usam o banco configurado para a aplicação.
Os testes de interface usam Chrome ou Edge em modo headless, sem acessar o banco. Se necessário, defina `BROWSER_PATH` com o caminho do navegador.

### Se o PowerShell bloquear a ativação do ambiente

Você pode dispensar a ativação usando os executáveis diretamente:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe init_db.py
.\.venv\Scripts\python.exe app.py
```

Ou execute `Set-ExecutionPolicy -Scope Process Bypass` somente para a sessão atual antes de ativar o venv.

## Banco de dados via phpMyAdmin

Após rodar `python init_db.py`, acesse `http://localhost/phpmyadmin`, selecione `doceria_online` e veja as tabelas `categorias`, `produtos`, `administradores`, `pedidos`, `itens_pedido`.

O arquivo `sql/banco.sql` também permite **importar manualmente** as tabelas e os produtos no phpMyAdmin (aba **Importar**). Mas a importação manual **não cria o administrador**; execute `python init_db.py` depois para criá-lo.

> XAMPP normalmente utiliza **MariaDB**, compatível com as consultas SQL/MySQL usadas neste projeto. `phpMyAdmin` é a ferramenta de administração; o SGBD é o MySQL/MariaDB.

## Estrutura
```text
doceria_online/
├── app.py                # Rotas Flask / API REST
├── init_db.py            # Instala esquema e usuário admin
├── requirements.txt      # Dependências Python
├── .env.example          # Configurações de exemplo
├── .gitignore
├── sql/banco.sql         # Estrutura SQL e produtos iniciais
├── templates/
│   ├── index.html        # Cardápio
│   ├── login.html        # Login
│   └── admin.html        # Painel
└── static/
    ├── css/style.css
    └── js/
        ├── publico.js
        ├── login.js
        └── admin.js
```

## Endpoints principais

| Método | Rota | Função |
| --- | --- | --- |
| GET | `/api/categorias` | Listar categorias |
| GET | `/api/produtos` | Listar produtos |
| POST | `/api/pedidos` | Criar pedido |
| POST | `/api/login` | Autenticar administrador |
| POST | `/api/logout` | Encerrar sessão |
| POST | `/api/produtos` | Criar produto (admin) |
| PUT | `/api/produtos/<id>` | Editar produto (admin) |
| DELETE | `/api/produtos/<id>` | Excluir produto (admin) |
| GET | `/api/pedidos` | Listar pedidos (admin) |
| PATCH | `/api/pedidos/<id>/status` | Alterar status (admin) |
| GET | `/api/dashboard` | Contagens e faturamento (faturamento apenas para administradores) |
| POST | `/api/usuarios` | Cadastrar administrador ou funcionário (admin) |
| GET | `/api/usuarios` | Listar usuários (admin) |
| PUT | `/api/usuarios/<id>` | Editar usuário, perfil e senha opcional (admin) |
| GET | `/api/imagens/<id>` | Exibir imagem de produto |

## Observações para apresentação
O navegador usa JavaScript `fetch()` para solicitar dados ao Flask. Flask consulta o MySQL via PyMySQL. O painel administrativo também consome a API. O total de cada pedido é calculado no Python a partir dos preços gravados no banco, não do valor informado pelo navegador.

Na resposta de `/api/dashboard`, `faturamento` substitui `lucro` e representa a soma dos totais concluídos.

O sistema é uma **demonstração acadêmica local**, sem pagamento online, envio de WhatsApp ou hospedagem pública. Para produção seriam necessários HTTPS, proteção contra tentativas repetidas de login, controles de privacidade de clientes, monitoramento e outras medidas de segurança.
