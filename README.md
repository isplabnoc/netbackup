# NetAudit Backup

Plataforma enterprise de backup e auditoria de equipamentos de rede, inspirada no Oxidized, com FastAPI, PostgreSQL, SQLAlchemy 2.0, Alembic, APScheduler, Netmiko, Paramiko, Bootstrap 5, HTMX e Nginx.

## Recursos

- API REST com Swagger em `/docs`.
- Interface web com login obrigatório.
- RBAC: `Admin`, `Operator`, `Viewer`.
- Cadastro multi-vendor: Dell OS6, Dell OS10, MikroTik, Cisco IOS, Cisco NXOS, FortiGate, F5 BIG-IP, Huawei VRP e Juniper JunOS.
- Grupos de credenciais com senha criptografada via Fernet.
- Engine paralela com `ThreadPoolExecutor`, padrão de 30 workers.
- Backups versionados em `backups/YYYY/MM/DD/device/`.
- Diff automático com `difflib` e visualização HTML.
- Dashboard com Chart.js.
- Scheduler diário com APScheduler.
- Notificações Telegram e Evolution API.
- Logs JSON em `logs/app.log` e `logs/backup.log`.

## Estrutura

```text
app/
├── api/
├── core/
├── database/
├── models/
├── repositories/
├── schemas/
├── services/
├── workers/
├── templates/
├── static/
└── integrations/
```

## Execução local com Docker

1. Crie o `.env`:

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copie a chave gerada para `FERNET_KEY` e troque `SECRET_KEY` por um valor longo e aleatório.

2. Suba o ambiente:

```bash
docker compose up --build
```

3. Crie o primeiro administrador:

```bash
curl -X POST http://localhost:8080/api/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","full_name":"Admin","password":"ChangeMe123!","role":"Admin"}'
```

4. Acesse:

- Web: http://localhost:8080
- Swagger: http://localhost:8080/docs
- PostgreSQL local: `localhost:5432`

## Execução local sem Docker

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Use um PostgreSQL acessível em `DATABASE_URL`.

## Produção

1. Configure `.env` com segredos reais, banco dedicado e tokens de notificação.
2. Ajuste Nginx para TLS ou coloque o compose atrás de um proxy TLS corporativo.
3. Execute:

```bash
docker compose up -d --build
docker compose exec app alembic upgrade head
```

## Instalação Automatizada Em Debian 13 Limpo

Execute como `root` dentro da pasta do projeto:

```bash
sudo bash scripts/install_debian13.sh
```

Ou instale diretamente de um repositório Git:

```bash
curl -fsSL https://seu-dominio/install_debian13.sh -o install_debian13.sh
sudo REPO_URL=https://github.com/sua-org/netbackup-pro.git \
  REPO_REF=main \
  APP_PORT=8080 \
  ADMIN_EMAIL=admin@empresa.com \
  bash install_debian13.sh
```

Variáveis úteis:

```bash
APP_DIR=/opt/netbackup-pro
APP_PORT=8080
REPO_URL=https://github.com/sua-org/netbackup-pro.git
REPO_REF=main
ADMIN_EMAIL=admin@empresa.com
ADMIN_PASSWORD='senha-forte'
POSTGRES_PASSWORD='senha-forte-do-banco'
BACKUP_WORKERS=30
INSTALL_UFW=true
```

## Instalação No EasyPanel

O EasyPanel ja fornece proxy HTTPS, entao use `docker-compose.easypanel.yml`, sem o container Nginx.

1. Suba o projeto para um repositorio Git.
2. No EasyPanel, crie um projeto, por exemplo `netbackup`.
3. Crie um servico Compose apontando para o arquivo:

```text
docker-compose.easypanel.yml
```

4. Configure as variaveis de ambiente:

```bash
APP_NAME=NetBackup Pro
ENVIRONMENT=production
POSTGRES_DB=netaudit
POSTGRES_USER=netaudit
POSTGRES_PASSWORD=troque-esta-senha
DATABASE_URL=postgresql+psycopg://netaudit:troque-esta-senha@postgres:5432/netaudit
SECRET_KEY=troque-por-um-segredo-longo
FERNET_KEY=gere-com-python-ou-openssl
ACCESS_TOKEN_EXPIRE_MINUTES=480
BACKUP_WORKERS=30
DAILY_BACKUP_CRON_HOUR=2
DAILY_BACKUP_CRON_MINUTE=0
```

Gere `FERNET_KEY` em qualquer maquina com Python:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

5. Configure o dominio do servico apontando para a porta interna:

```text
8000
```

6. Depois do deploy, crie o admin inicial:

```bash
curl -X POST https://backup.seudominio.com/api/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@empresa.com","full_name":"Admin","password":"SenhaForteAqui","role":"Admin"}'
```

7. Acesse:

```text
https://backup.seudominio.com/login
```

## Publicar No GitHub

Crie um token no GitHub com permissao para criar repositorio e fazer push. Depois execute:

```bash
export GITHUB_TOKEN='ghp_seu_token'
REPO_NAME=netbackup-pro PRIVATE=true bash scripts/publish_github.sh
```

Para publicar em uma organizacao:

```bash
export GITHUB_TOKEN='ghp_seu_token'
GITHUB_ORG=sua-org REPO_NAME=netbackup-pro PRIVATE=true bash scripts/publish_github.sh
```

No EasyPanel, use o repositorio criado e selecione o arquivo:

```text
docker-compose.easypanel.yml
```

4. Rotacione e proteja:

- `SECRET_KEY`
- `FERNET_KEY`
- credenciais dos equipamentos
- tokens Telegram/Evolution

## Endpoints principais

- `GET /api/devices`
- `POST /api/devices`
- `PUT /api/devices/{id}`
- `DELETE /api/devices/{id}`
- `GET /api/backups`
- `POST /api/backups/run`
- `GET /api/diffs`
- `GET /api/reports`

## Drivers

Cada driver implementa:

```python
connect()
backup()
disconnect()
```

Para adicionar um vendor, crie um arquivo em `app/services/drivers/` e registre a classe em `DRIVER_REGISTRY`.
