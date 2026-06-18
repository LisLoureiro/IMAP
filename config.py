"""Configuração lida de variáveis de ambiente (.env opcional)."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    # Conexão IMAP — conta Hotmail/Outlook (Microsoft)
    IMAP_HOST = os.getenv("IMAP_HOST", "outlook.office365.com")
    IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USER = os.getenv("IMAP_USER", "lis-ls@hotmail.com")
    IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
    IMAP_MAILBOX = os.getenv("IMAP_MAILBOX", "INBOX")
    FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "150"))

    # Só ingere emails cujo remetente contenha este texto (notificações Monday).
    # Deixe vazio para ingerir todos os emails.
    MONDAY_SENDER = os.getenv("MONDAY_SENDER", "monday.com")

    # OAuth2 (Microsoft) para IMAP — necessário para Hotmail/Outlook.
    # MS_CLIENT_ID vem do registro de app no Azure/Entra (veja o README).
    MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
    MS_AUTHORITY = os.getenv("MS_AUTHORITY", "https://login.microsoftonline.com/consumers")
    MS_SCOPES = ["https://outlook.office.com/IMAP.AccessAsUser.All"]

    # PostgreSQL — use DATABASE_URL ou os campos individuais.
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    PG_HOST = os.getenv("POSTGRES_HOST", "db")
    PG_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    PG_DB = os.getenv("POSTGRES_DB", "solicitacoes")
    PG_USER = os.getenv("POSTGRES_USER", "postgres")
    PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

    @classmethod
    def dsn(cls):
        if cls.DATABASE_URL:
            return cls.DATABASE_URL
        return (
            f"host={cls.PG_HOST} port={cls.PG_PORT} dbname={cls.PG_DB} "
            f"user={cls.PG_USER} password={cls.PG_PASSWORD}"
        )


# Estágios "inferidos" quando a notificação não traz um valor de status do Monday.
# (O status real do Monday, quando capturado, é exibido como veio.)
STATUS_INFERIDO = ["Criada", "Em andamento", "Sem atividade recente"]

# Paleta para os selos de status. Valores não mapeados recebem cor neutra.
STATUS_COR = {
    "Criada": "#2f6db3",
    "Em andamento": "#b58a16",
    "Sem atividade recente": "#7a7f8a",
    # status comuns do Monday (PT/EN) — ajuste aos do seu quadro:
    "Concluído": "#3d7a3d", "Done": "#3d7a3d", "Feito": "#3d7a3d",
    "Travado": "#c0532b", "Stuck": "#c0532b", "Parado": "#c0532b",
    "Trabalhando nisso": "#b58a16", "Working on it": "#b58a16",
}
COR_NEUTRA = "#5d6678"
