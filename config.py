"""Configuração lida de variáveis de ambiente (.env opcional)."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    # Conexão IMAP — conta corporativa VERT (Microsoft 365)
    IMAP_HOST     = os.getenv("IMAP_HOST", "outlook.office365.com")
    IMAP_PORT     = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USER     = os.getenv("IMAP_USER", "lis.sousa@vert-capital.com")
    IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
    IMAP_MAILBOX  = os.getenv("IMAP_MAILBOX", "INBOX")
    FETCH_LIMIT   = int(os.getenv("FETCH_LIMIT", "150"))

    # Filtra por remetente. Vazio = ingere tudo.
    # Na VERT as notificações do Monday chegam de crm@vert-capital.com,
    # não de monday.com — deixamos vazio para não bloquear.
    MONDAY_SENDER = os.getenv("MONDAY_SENDER", "")

    # OAuth2 Microsoft 365 — conta corporativa.
    MS_CLIENT_ID  = os.getenv("MS_CLIENT_ID", "")
    # Conta corporativa (tenant da VERT): use "common" ou o tenant ID específico.
    MS_AUTHORITY  = os.getenv(
        "MS_AUTHORITY",
        "https://login.microsoftonline.com/common",
    )
    MS_SCOPES = ["https://outlook.office.com/IMAP.AccessAsUser.All"]

    # PostgreSQL
    DATABASE_URL  = os.getenv("DATABASE_URL", "")
    PG_HOST       = os.getenv("POSTGRES_HOST", "db")
    PG_PORT       = int(os.getenv("POSTGRES_PORT", "5432"))
    PG_DB         = os.getenv("POSTGRES_DB", "solicitacoes")
    PG_USER       = os.getenv("POSTGRES_USER", "postgres")
    PG_PASSWORD   = os.getenv("POSTGRES_PASSWORD", "postgres")

    @classmethod
    def dsn(cls):
        if cls.DATABASE_URL:
            return cls.DATABASE_URL
        return (
            f"host={cls.PG_HOST} port={cls.PG_PORT} dbname={cls.PG_DB} "
            f"user={cls.PG_USER} password={cls.PG_PASSWORD}"
        )


# Estágios inferidos (quando a notificação não traz status real do Monday)
STATUS_INFERIDO = ["Criada", "Em andamento", "Sem atividade recente"]

# Paleta de selos — ajuste aos status reais dos seus boards Monday
STATUS_COR = {
    # Inferidos
    "Criada":                "#2f6db3",
    "Em andamento":          "#b58a16",
    "Sem atividade recente": "#7a7f8a",
    # Status Monday PT
    "Concluído":             "#3d7a3d",
    "Feito":                 "#3d7a3d",
    "Liquidada":             "#3d7a3d",   # VERT: operação liquidada
    "Aprovado":              "#3d7a3d",
    "Travado":               "#c0532b",
    "Parado":                "#c0532b",
    "Pendente":              "#b58a16",
    "Cancelado":             "#7a7f8a",
    "Rejeitado":             "#7a7f8a",
    # Status Monday EN (alguns boards usam inglês)
    "Done":                  "#3d7a3d",
    "Stuck":                 "#c0532b",
    "Working on it":         "#b58a16",
}
COR_NEUTRA = "#5d6678"
