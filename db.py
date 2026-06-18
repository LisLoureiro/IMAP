"""Persistência em PostgreSQL.

Guardamos cada NOTIFICAÇÃO (email do Monday). A 'solicitação' é montada
agregando as notificações que compartilham a mesma chave de item (pulse_id).

A interface pública é a mesma da versão anterior, então app.py não muda:
    init_db, inserir_se_nova, todas_notificacoes, total_notificacoes, limpar_tudo
"""
import time
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from config import Config


@contextmanager
def _con():
    con = psycopg2.connect(Config.dsn())
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(tentativas=10, espera=2):
    """Cria a tabela. Tenta algumas vezes para esperar o Postgres subir (Docker)."""
    ultimo_erro = None
    for _ in range(tentativas):
        try:
            with _con() as con, con.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notificacoes (
                        id            SERIAL PRIMARY KEY,
                        message_id    TEXT UNIQUE NOT NULL,
                        chave         TEXT NOT NULL,
                        pulse_id      TEXT,
                        board_id      TEXT,
                        link          TEXT,
                        item_nome     TEXT,
                        ator          TEXT,
                        tipo          TEXT,
                        status_valor  TEXT,
                        assunto       TEXT,
                        resumo        TEXT,
                        corpo         TEXT,
                        data_email    TEXT,
                        criado_em     TIMESTAMPTZ DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_chave ON notificacoes(chave)"
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_cache (
                        chave TEXT PRIMARY KEY,
                        valor TEXT
                    )
                    """
                )
            return
        except psycopg2.OperationalError as e:
            ultimo_erro = e
            time.sleep(espera)
    raise RuntimeError(f"Não foi possível conectar ao PostgreSQL: {ultimo_erro}")


def inserir_se_nova(d):
    """Insere se o Message-ID for novo. Retorna True se inseriu (False se já existia)."""
    with _con() as con, con.cursor() as cur:
        cur.execute(
            """
            INSERT INTO notificacoes
              (message_id, chave, pulse_id, board_id, link, item_nome, ator,
               tipo, status_valor, assunto, resumo, corpo, data_email)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (message_id) DO NOTHING
            RETURNING id
            """,
            (
                d["message_id"], d["chave"], d["pulse_id"], d["board_id"], d["link"],
                d["item_nome"], d["ator"], d["tipo"], d["status_valor"], d["assunto"],
                d["resumo"], d["corpo"], d["data_email"],
            ),
        )
        return cur.fetchone() is not None


def todas_notificacoes():
    with _con() as con, con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM notificacoes ORDER BY data_email DESC NULLS LAST"
        )
        return [dict(r) for r in cur.fetchall()]


def total_notificacoes():
    with _con() as con, con.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM notificacoes")
        return cur.fetchone()[0]


def limpar_tudo():
    with _con() as con, con.cursor() as cur:
        cur.execute("TRUNCATE notificacoes RESTART IDENTITY")


# --- Cache do token OAuth (MSAL) ---
def carregar_cache():
    with _con() as con, con.cursor() as cur:
        cur.execute("SELECT valor FROM app_cache WHERE chave='msal'")
        row = cur.fetchone()
        return row[0] if row else ""


def salvar_cache(texto):
    with _con() as con, con.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_cache (chave, valor) VALUES ('msal', %s)
            ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor
            """,
            (texto,),
        )


def apagar_cache():
    with _con() as con, con.cursor() as cur:
        cur.execute("DELETE FROM app_cache WHERE chave='msal'")
