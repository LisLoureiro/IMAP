"""Interpreta uma notificação do Monday (email) e extrai os campos úteis.

As notificações do Monday variam de formato e idioma (PT/EN). As regras abaixo
são best-effort e foram pensadas para serem fáceis de ajustar quando você
testar com emails reais — todos os padrões ficam reunidos aqui no topo.

Campos devolvidos:
    pulse_id      -> id do item no Monday (chave para agrupar a solicitação)
    board_id      -> id do quadro
    link          -> URL do item
    item_nome     -> nome da solicitação
    ator          -> quem realizou a ação (quando identificável)
    tipo          -> criada | atualizacao | status | prazo | mencao | outro
    status_valor  -> novo valor de status, quando a notificação for de status
"""
import re

# --- Links do Monday: .../boards/<board>/pulses/<pulse> ---
RE_PULSE = re.compile(r"monday\.com/[^\s\"'<>]*?pulses/(\d+)", re.I)
RE_BOARD = re.compile(r"monday\.com/[^\s\"'<>]*?boards/(\d+)", re.I)
RE_LINK = re.compile(r"https?://[^\s\"'<>]*monday\.com[^\s\"'<>]*", re.I)

# --- Nome do item entre aspas (retas ou tipográficas) ---
RE_ASPAS = re.compile(r"[\"'“‘]([^\"'”’\n]{2,80})[\"'”’]")

# --- Classificação do tipo de notificação (ordem = prioridade) ---
TIPO_REGRAS = [
    ("status",      [r"status", r"movid[oa] para", r"moved to", r"label"]),
    ("prazo",       [r"prazo", r"data de", r"vence", r"venceu", r"due date",
                     r"overdue", r"timeline", r"date changed"]),
    ("criada",      [r"criou", r"criad", r"novo item", r"new item", r"new pulse",
                     r"created", r"adicionou", r"added a new"]),
    ("mencao",      [r"mencionou", r"mentioned", r"atribuiu", r"assigned",
                     r"marcou voc[êe]", r"tagged you"]),
    ("atualizacao", [r"atualizaç", r"atualizou", r"update", r"publicou",
                     r"comentou", r"comment", r"respondeu", r"replied", r"reply"]),
]

# --- Captura do novo valor de status ---
RE_STATUS_VALOR = [
    re.compile(r"status[^\n]{0,40}?(?:para|to|→|->)\s*[\"'“]?([^\"'”\n\.;]{1,40})", re.I),
    re.compile(r"(?:movid[oa] para|moved to)\s+[\"'“]?([^\"'”\n\.;]{1,40})", re.I),
]

# --- Quem realizou a ação (início do corpo: "Fulano <verbo> ...") ---
RE_ATOR = re.compile(
    r"^\s*([A-ZÀ-Ý][\wÀ-ÿ.\- ]{1,40}?)\s+"
    r"(?:criou|atualizou|mencionou|alterou|mudou|comentou|adicionou|moveu|"
    r"created|changed|mentioned|posted|assigned|moved|commented|replied)",
    re.M,
)


def _primeiro(regex, texto):
    m = regex.search(texto)
    return m.group(1).strip() if m else ""


def _classificar(texto):
    t = texto.lower()
    for tipo, chaves in TIPO_REGRAS:
        if any(re.search(k, t) for k in chaves):
            return tipo
    return "outro"


def _status_valor(texto):
    for regex in RE_STATUS_VALOR:
        m = regex.search(texto)
        if m:
            return m.group(1).strip(" '\"“”.")
    return ""


def _item_nome(assunto, corpo, link):
    # Pode haver mais de um trecho entre aspas (ex.: valor do status + nome do
    # item). Preferimos o que vem logo após "em / no / na / in / on".
    for fonte in (assunto, corpo):
        candidatos = list(RE_ASPAS.finditer(fonte))
        if not candidatos:
            continue
        for m in candidatos:
            antes = fonte[max(0, m.start() - 6):m.start()].lower()
            if re.search(r"\b(em|no|na|in|on)\s*$", antes):
                return m.group(1).strip()
        # senão, o trecho citado mais longo (costuma ser o nome do item)
        return max((m.group(1).strip() for m in candidatos), key=len)
    # sem aspas: limpa prefixos comuns do assunto
    limpo = re.sub(r"^(re:|fwd:|enc:)\s*", "", assunto, flags=re.I).strip()
    limpo = re.sub(r"\s*[-–|]\s*monday\.com.*$", "", limpo, flags=re.I)
    return limpo or "(sem título)"


def _ator(corpo, remetente_nome):
    a = _primeiro(RE_ATOR, corpo)
    if a:
        return a
    nome = re.sub(r"\s*via monday\.com\s*", "", remetente_nome or "", flags=re.I).strip()
    return nome or "(desconhecido)"


def analisar(email_dict):
    """Recebe o dict de um email (de email_client) e devolve os campos Monday."""
    assunto = email_dict.get("assunto", "")
    corpo = email_dict.get("corpo", "")
    base = f"{assunto}\n{corpo}"

    pulse_id = _primeiro(RE_PULSE, base)
    board_id = _primeiro(RE_BOARD, base)
    link = ""
    m = RE_LINK.search(base)
    if m:
        link = m.group(0)

    tipo = _classificar(base)
    item_nome = _item_nome(assunto, corpo, link)

    # chave de agrupamento: pulse_id se houver, senão o nome normalizado
    chave = pulse_id or ("nome:" + re.sub(r"\s+", " ", item_nome.lower()).strip())

    return {
        "chave": chave,
        "pulse_id": pulse_id,
        "board_id": board_id,
        "link": link,
        "item_nome": item_nome,
        "ator": _ator(corpo, email_dict.get("remetente_nome", "")),
        "tipo": tipo,
        "status_valor": _status_valor(base) if tipo == "status" else "",
    }
