# Deploy No EasyPanel App

Use este modelo quando quiser instalar o NetBackup Pro da mesma forma que o NOC360: **App via GitHub**, build pelo **Dockerfile** da raiz e proxy HTTPS do EasyPanel apontando para a porta interna `8000`.

## GitHub

```text
Owner: isplabnoc
Repository: netbackup
Branch: main
Build Path: /
Build Type: Dockerfile
Dockerfile: Dockerfile
```

## Banco De Dados

Crie antes um serviço **Postgres** no EasyPanel.

Valores sugeridos:

```text
Database: netaudit
Username: netaudit
Password: gere uma senha forte
```

Depois use a URL interna do serviço no `DATABASE_URL`. O hostname depende do nome do serviço criado no EasyPanel. Se o serviço Postgres se chamar `netbackup-postgres`, use:

```bash
DATABASE_URL=postgresql+psycopg://netaudit:SENHA_FORTE@netbackup-postgres:5432/netaudit
```

## App

Crie um **App** no EasyPanel:

```text
Source: GitHub
Owner: isplabnoc
Repository: netbackup
Branch: main
Build Path: /
Build: Dockerfile
Proxy Port: 8000
```

## Environment

Configure no EasyPanel:

```bash
APP_NAME=NetBackup Pro
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://netaudit:SENHA_FORTE@netbackup-postgres:5432/netaudit
SECRET_KEY=troque-por-um-segredo-longo
FERNET_KEY=gere-uma-chave-fernet
ACCESS_TOKEN_EXPIRE_MINUTES=480
BACKUP_ROOT=/app/backups
BACKUP_WORKERS=30
DAILY_BACKUP_CRON_HOUR=2
DAILY_BACKUP_CRON_MINUTE=0
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EVOLUTION_API_URL=
EVOLUTION_API_TOKEN=
EVOLUTION_API_INSTANCE=
```

Gere `FERNET_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Gere `SECRET_KEY`:

```bash
openssl rand -base64 48
```

## Mounts

No EasyPanel, adicione volumes persistentes:

```text
Volume: backups -> /app/backups
Volume: logs    -> /app/logs
```

Sem esses volumes, backups e logs podem ser perdidos em redeploy.

## Domain & Proxy

Configure o domínio do app e use:

```text
Proxy Port: 8000
```

O EasyPanel cuidará do HTTPS/Let's Encrypt.

## Primeiro Admin

Depois do deploy:

```bash
curl -X POST https://backup.seudominio.com/api/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@empresa.com","full_name":"Admin","password":"SenhaForteAqui","role":"Admin"}'
```

Acesse:

```text
https://backup.seudominio.com/login
```

## Observações

- O container executa `alembic upgrade head` automaticamente ao iniciar.
- O app espera o banco responder antes de iniciar.
- Não use `docker-compose.easypanel.yml` neste modo. Ele fica disponível apenas para quem preferir Compose Service.
