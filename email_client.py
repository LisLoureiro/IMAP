"""Cliente IMAP usando apenas a biblioteca padrão (imaplib + email).

Baixa os emails mais recentes da caixa e devolve dicts com os campos já
extraídos (via módulo `extracao`).
"""
import email
import imaplib
import re
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

from config import Config


# --------------------------- parsing de texto ------------------------------
class _ExtratorTexto(HTMLParser):
    def __init__(self):
        super().__init__()
        self._partes, self._ignorar = [], False

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head"):
            self._ignorar = True
        if tag in ("br", "p", "div", "tr", "li"):
            self._partes.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head"):
            self._ignorar = False

    def handle_data(self, data):
        if not self._ignorar:
            self._partes.append(data)

    def texto(self):
        return "".join(self._partes)


def _html_para_texto(html):
    p = _ExtratorTexto()
    try:
        p.feed(html)
        return p.texto()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


def _decodificar(valor):
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(valor)))
    except Exception:
        return valor


def _limpar(t):
    t = t.replace("\r", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _payload_str(parte):
    try:
        raw = parte.get_payload(decode=True) or b""
        charset = parte.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")
    except Exception:
        return ""


def _extrair_corpo(msg):
    plano, html = "", ""
    if msg.is_multipart():
        for parte in msg.walk():
            if "attachment" in str(parte.get("Content-Disposition") or "").lower():
                continue
            ctype = parte.get_content_type()
            if ctype == "text/plain" and not plano:
                plano = _payload_str(parte)
            elif ctype == "text/html" and not html:
                html = _payload_str(parte)
    else:
        if msg.get_content_type() == "text/html":
            html = _payload_str(msg)
        else:
            plano = _payload_str(msg)
    if plano:
        return _limpar(plano)
    if html:
        return _limpar(_html_para_texto(html))
    return ""


def _resumo(corpo, limite=240):
    linhas = []
    for linha in corpo.split("\n"):
        l = linha.strip()
        if l.startswith(">"):
            continue
        if re.match(r"^(em .*escreveu:|on .*wrote:|de:|from:)", l, re.I):
            break
        if l:
            linhas.append(l)
        if sum(len(x) for x in linhas) > limite:
            break
    r = " ".join(linhas)
    if len(r) > limite:
        r = r[:limite].rsplit(" ", 1)[0] + "…"
    return r or "(sem conteúdo de texto)"


# --------------------------- conexão IMAP ----------------------------------
def buscar_emails(conexao=None, limite=None, oauth_token=None):
    """Conecta via IMAP e devolve lista de dicts dos emails mais recentes.

    `conexao` (opcional): dict com host, port, user, password, mailbox para
    sobrepor o .env.
    `oauth_token` (opcional): access_token OAuth2 — se fornecido, usa XOAUTH2
    (necessário para Hotmail/Outlook). Senão, tenta login por senha.
    Lança RuntimeError com mensagem amigável em caso de erro.
    """
    c = conexao or {}
    host = c.get("host") or Config.IMAP_HOST
    port = int(c.get("port") or Config.IMAP_PORT)
    user = c.get("user") or Config.IMAP_USER
    senha = c.get("password") or Config.IMAP_PASSWORD
    mailbox = c.get("mailbox") or Config.IMAP_MAILBOX
    limite = limite or Config.FETCH_LIMIT

    if not user:
        raise RuntimeError("Informe o email da conta.")
    if not oauth_token and not senha:
        raise RuntimeError("Conecte a conta (OAuth2) ou informe uma senha.")

    try:
        con = imaplib.IMAP4_SSL(host, port)
    except Exception as e:
        raise RuntimeError(f"Não foi possível conectar a {host}:{port} — {e}")

    try:
        if oauth_token:
            try:
                auth = f"user={user}\x01auth=Bearer {oauth_token}\x01\x01".encode()
                con.authenticate("XOAUTH2", lambda _=None: auth)
            except imaplib.IMAP4.error as e:
                raise RuntimeError(
                    "Falha no login OAuth2 (XOAUTH2). Confira o registro do app no "
                    "Azure, a permissão IMAP.AccessAsUser.All e se a conta autorizou. "
                    "Detalhe: " + str(e)
                )
        else:
            try:
                con.login(user, senha)
            except imaplib.IMAP4.error as e:
                raise RuntimeError(
                    "Falha no login IMAP por senha. Em contas Hotmail/Outlook a senha "
                    "simples não funciona mais — use OAuth2. Detalhe: " + str(e)
                )

        if con.select(mailbox)[0] != "OK":
            raise RuntimeError(f"Não foi possível abrir a pasta '{mailbox}'.")

        status, dados = con.search(None, "ALL")
        if status != "OK":
            return []
        ids = dados[0].split()[-limite:]

        emails = []
        for num in reversed(ids):
            st, msg_data = con.fetch(num, "(RFC822)")
            if st != "OK" or not msg_data or not msg_data[0]:
                continue
            emails.append(_montar(email.message_from_bytes(msg_data[0][1]), num.decode()))
        return emails
    finally:
        try:
            con.close(); con.logout()
        except Exception:
            pass


def _montar(msg, uid):
    assunto = _decodificar(msg.get("Subject")) or "(sem assunto)"
    nome, endereco = parseaddr(_decodificar(msg.get("From")))
    message_id = (msg.get("Message-ID") or f"uid-{uid}-{assunto[:30]}").strip()
    try:
        dt = parsedate_to_datetime(msg.get("Date"))
        data_iso = dt.isoformat(timespec="seconds") if dt else ""
    except Exception:
        data_iso = ""

    corpo = _extrair_corpo(msg)
    return {
        "message_id": message_id,
        "remetente": endereco,
        "remetente_nome": nome or endereco,
        "assunto": assunto,
        "data_email": data_iso,
        "corpo": corpo,
        "resumo": _resumo(corpo),
    }
