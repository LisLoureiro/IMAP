# Painel de Solicitações (notificações do Monday por email)

Lê as **notificações do Monday** que chegam na sua caixa de email (via IMAP),
agrupa por solicitação (o item do Monday) e mostra um painel com o **status
atual** de cada uma e a linha do tempo dos eventos.

## Como funciona

1. **Sincronizar** baixa os emails mais recentes via IMAP.
2. Mantém só os que são notificações do Monday (remetente contém `monday.com`
   ou o corpo tem um link `monday.com`).
3. Cada email vira uma *notificação*; o link do item (`.../pulses/<id>`) é a
   chave que junta todas as notificações da mesma solicitação.
4. O painel agrega: quem criou, datas, nº de eventos, **status atual** (último
   valor capturado de "mudou Status para X"; quando não há, infere um estágio)
   e a linha do tempo.

## Rodando com Docker (recomendado)

Sobe o app e o PostgreSQL juntos.

```bash
cp .env.example .env        # preencha as credenciais do email
docker compose up --build
```

Abre em `http://localhost:8501`. O banco roda no serviço `db` (Postgres 16) e os
dados ficam no volume `pgdata` (persistem entre reinícios). O app já aponta para
o `db` automaticamente.

Para parar: `docker compose down` (ou `docker compose down -v` para apagar também
o volume do banco).

## Rodando sem Docker

Precisa de um PostgreSQL acessível.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # preencha email e aponte o Postgres (POSTGRES_HOST/PORT ou DATABASE_URL)
streamlit run app.py
```

## Conectar a conta Hotmail/Outlook (OAuth2)

Contas pessoais Hotmail/Outlook **não aceitam mais login por senha** no IMAP — a
Microsoft exige OAuth2. É preciso um registro de app gratuito no Azure (uma vez):

1. Acesse https://portal.azure.com → **Microsoft Entra ID** → **Registros de
   aplicativo** → **Novo registro**.
2. Nome: qualquer (ex.: "Painel Solicitações"). Em *Tipos de conta com suporte*
   escolha **Apenas contas pessoais da Microsoft**. Sem URI de redirecionamento.
   Clique em **Registrar**.
3. Copie o **ID do aplicativo (cliente)** e coloque em `MS_CLIENT_ID` no `.env`.
4. Vá em **Autenticação** → *Configurações avançadas* → **Permitir fluxos de
   cliente público** → **Sim** → **Salvar** (necessário para o login por código).
5. A permissão `IMAP.AccessAsUser.All` é consentida no momento do login; não
   precisa pré-cadastrar para conta pessoal.

Depois, no app: barra lateral → **Iniciar login Microsoft** → abra o link
mostrado, digite o código e autorize → **Concluir login**. O token fica guardado
no PostgreSQL e é renovado sozinho (não precisa logar de novo a cada uso).

> Conta corporativa/escolar: troque `MS_AUTHORITY` para
> `https://login.microsoftonline.com/common` (ou o tenant) e, no registro,
> permita contas da organização.

## Calibração do parser (importante)

As notificações do Monday variam de formato e idioma. As regras de parsing
estão todas em **`monday_parser.py`**, no topo do arquivo, fáceis de ajustar:

- `TIPO_REGRAS` — classifica o tipo de notificação (criada/atualização/status…).
- `RE_STATUS_VALOR` — captura o novo valor de status ("mudou Status para X").
- `RE_ATOR` — identifica quem fez a ação.
- `STATUS_COR` (em `config.py`) — cores dos selos por status.

Se algum campo vier errado, me mande **um email de notificação real** (texto)
e eu acerto os padrões.

## Arquivos

- `app.py` — interface Streamlit (painel).
- `email_client.py` — conexão IMAP e leitura/limpeza dos emails.
- `monday_parser.py` — interpreta as notificações do Monday.
- `aggregacao.py` — monta as solicitações a partir das notificações.
- `db.py` — persistência em PostgreSQL.
- `auth_ms.py` — login OAuth2 com a Microsoft (MSAL, device-code).
- `config.py` — configuração (IMAP, OAuth, Postgres) e cores de status.
- `Dockerfile` / `docker-compose.yml` — empacotamento (app + Postgres).
