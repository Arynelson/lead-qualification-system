# Deploy Guide — Lead Qualification System no VPS (Contabo)

**Ary Hauffe Neto** · Atualizado: March 2026

Este guia cobre tudo: subir o código, configurar variáveis, rodar os containers, HTTPS automático com Caddy, e importar o workflow no n8n.

---

## Pré-requisitos (VPS já deve ter)

- Ubuntu 22.04 LTS
- Docker + Docker Compose v2 instalados (`docker compose version` para confirmar)
- Firewall: portas 80 e 443 abertas (HTTP/HTTPS), porta 22 (SSH)
- Domínio `makeit.bot` apontando para o IP do VPS (DNS configurado)

---

## Arquitetura no VPS

```
Internet
    │
    ▼
Caddy (443/80)  ← HTTPS automático via Let's Encrypt
    │
    ├── n8n.makeit.bot  → n8n:5678
    └── api.makeit.bot  → fastapi:8000

PostgreSQL (interno, não exposto)
    ├── database: leads  (FastAPI)
    └── database: n8n    (n8n)
```

---

## Parte 1 — Subir o código para o VPS

### Opção A: GitHub (recomendado)

No VPS:
```bash
# Clonar o repositório
cd /opt
git clone https://github.com/arynelson/lead-qualification-system.git
cd lead-qualification-system
```

### Opção B: SCP (se o repo ainda não está público)

No teu computador local:
```bash
scp -r /caminho/para/lead-qualification-system root@SEU_IP_VPS:/opt/
```

---

## Parte 2 — Configurar variáveis de ambiente

No VPS, dentro do diretório do projeto:

```bash
cd /opt/lead-qualification-system
cp .env.example .env
nano .env
```

Preenche com os valores reais:

```env
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:SENHA_FORTE@postgres:5432/leads

# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-XXXX

# n8n
N8N_ENCRYPTION_KEY=gera-uma-chave-aleatoria-de-32-chars

# App
APP_ENV=production
```

Para gerar a chave de encriptação do n8n:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Parte 3 — Docker Compose de produção

Usa o arquivo `docker-compose.production.yml` (criado junto com este guia) em vez do `docker-compose.yml` padrão. As diferenças:
- Caddy incluído como reverse proxy com HTTPS automático
- n8n configurado com domínio real (não localhost)
- Comando do FastAPI sem `--reload` (produção)
- PostgreSQL sem porta exposta externamente (só interno)

```bash
# Subir todos os serviços
docker compose -f docker-compose.production.yml up -d

# Ver status
docker compose -f docker-compose.production.yml ps

# Ver logs
docker compose -f docker-compose.production.yml logs -f
```

---

## Parte 4 — Rodar as migrations do Alembic

Aguarda o postgres ficar saudável (10–15 segundos após o `up -d`) e então:

```bash
# Entrar no container do FastAPI
docker compose -f docker-compose.production.yml exec fastapi bash

# Dentro do container, rodar as migrations
alembic upgrade head

# Sair do container
exit
```

Para confirmar que as tabelas foram criadas:
```bash
docker compose -f docker-compose.production.yml exec postgres psql -U postgres -d leads -c "\dt"
```

Deves ver as tabelas: `leads`, `ai_scores`, `enrichments`, `lead_events`, `errors`.

---

## Parte 5 — Verificar que os serviços estão no ar

```bash
# FastAPI health check
curl https://api.makeit.bot/health

# Resposta esperada:
# {"status": "ok"}

# n8n — abre no browser
# https://n8n.makeit.bot
```

Se os domínios ainda não estiverem propagados, testa diretamente por IP:
```bash
curl http://SEU_IP_VPS:8000/health
# http://SEU_IP_VPS:5678  (no browser)
```

---

## Parte 6 — Configurar o n8n

### 6.1 Primeiro acesso

Abre `https://n8n.makeit.bot` no browser.

Cria o teu utilizador admin:
- Email: aryhauffe@gmail.com
- Password: usa uma senha forte

### 6.2 Importar os workflows

No n8n UI:
1. Menu lateral → **Workflows** → **Import from file**
2. Importa `n8n-workflows/lead-qualification.json`
3. Importa `n8n-workflows/error-handler.json`

### 6.3 Configurar credenciais no n8n

Após importar, precisas de configurar as credenciais:

**Anthropic:**
- Settings → Credentials → New → Anthropic
- API Key: a mesma do `.env`

**HTTP Request (webhook para FastAPI):**
- O workflow usa a URL interna: `http://fastapi:8000`
- Dentro da rede Docker, o FastAPI é acessível por esse nome

**Slack (para routing de leads):**
- Settings → Credentials → New → Slack
- Bot Token: obtido no Slack App dashboard

### 6.4 Ativar o workflow

1. Abre o workflow "Lead Qualification"
2. Clica no toggle **Inactive → Active**
3. Copia a webhook URL gerada (formato: `https://n8n.makeit.bot/webhook/XXXX`)

---

## Parte 7 — Testar o pipeline completo

```bash
# Enviar um lead de teste
curl -X POST https://n8n.makeit.bot/webhook/SEU_WEBHOOK_ID \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Lead",
    "email": "test@example.com",
    "company": "Example Corp",
    "title": "CTO",
    "source": "website"
  }'
```

Verifica:
1. No n8n → Executions: deves ver a execução bem-sucedida
2. No PostgreSQL: `SELECT * FROM leads ORDER BY created_at DESC LIMIT 1;`
3. No Slack: mensagem de routing chegou no canal correto

---

## Parte 8 — Gestão diária

### Ver logs em tempo real
```bash
# Todos os serviços
docker compose -f docker-compose.production.yml logs -f

# Só o FastAPI
docker compose -f docker-compose.production.yml logs -f fastapi

# Só o n8n
docker compose -f docker-compose.production.yml logs -f n8n
```

### Reiniciar um serviço
```bash
docker compose -f docker-compose.production.yml restart fastapi
docker compose -f docker-compose.production.yml restart n8n
```

### Deploy de nova versão (quando fizeres git push)
```bash
cd /opt/lead-qualification-system
git pull
docker compose -f docker-compose.production.yml build fastapi
docker compose -f docker-compose.production.yml up -d fastapi
# Migrations se houver alterações no schema:
docker compose -f docker-compose.production.yml exec fastapi alembic upgrade head
```

### Backup do PostgreSQL
```bash
docker compose -f docker-compose.production.yml exec postgres \
  pg_dump -U postgres leads > backup_leads_$(date +%Y%m%d).sql
```

---

## Resolução de problemas comuns

**Caddy não consegue certificado SSL:**
- Confirma que o DNS aponta para o IP do VPS: `dig api.makeit.bot`
- Confirma que as portas 80 e 443 estão abertas no firewall do Contabo

**Alembic migration falha:**
- Confirma que o PostgreSQL está saudável: `docker compose -f docker-compose.production.yml ps`
- Confirma que `DATABASE_URL` no `.env` tem a senha correta

**n8n não consegue chamar o FastAPI:**
- Dentro da rede Docker, o FastAPI é `http://fastapi:8000` (não localhost)
- Confirma no workflow que a URL dos HTTP Request nodes usa `fastapi` como host

**FastAPI container reiniciando em loop:**
- `docker compose -f docker-compose.production.yml logs fastapi`
- Geralmente é variável de ambiente em falta no `.env`

---

## URLs finais

| Serviço | URL |
|---|---|
| n8n (workflow editor) | https://n8n.makeit.bot |
| FastAPI docs | https://api.makeit.bot/docs |
| FastAPI health | https://api.makeit.bot/health |
| n8n webhook | https://n8n.makeit.bot/webhook/XXXX |

---

*Criado: March 2026*
