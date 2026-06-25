"""Interpreta notificacoes do Monday (email) e extrai os campos uteis.

Calibrado para o formato real da VERT Capital:
  - Remetente: crm@vert-capital.com (nao monday.com)
  - Assunto: "Automations escreveu uma atualizacao em FIDC WEG R$300MM (BB Asset)"
  - Corpo: bloco com board, status, data e conteudo da atualizacao
"""
import re

# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------
RE_PULSE       = re.compile(r"monday\.com/[^\s\"'<>]*?pulses/(\d+)", re.I)
RE_BOARD       = re.compile(r"monday\.com/[^\s\"'<>]*?boards/(\d+)", re.I)
RE_LINK_MONDAY = re.compile(r"https?://[^\s\"'<>]*monday\.com[^\s\"'<>]*", re.I)
RE_LINK_ANY    = re.compile(r"https?://[^\s\"'<>]{10,}", re.I)

# ---------------------------------------------------------------------------
# Nome do item
# ---------------------------------------------------------------------------
# Formato VERT: "... escreveu|criou... em NOME DO ITEM" — nome fica no fim do assunto
RE_NOME_ASSUNTO = re.compile(
    r"\bem\s+([^\n]{3,120}?)(?:\s*$|(?=\s*[-\u2013|]\s*monday))",
    re.I | re.M,
)
# Aspas tipograficas e retas
ASPAS_ABRE = '\u201c\u2018\u00ab"' + "'"
ASPAS_FECHA = '\u201d\u2019\u00bb"' + "'"
RE_ASPAS = re.compile(
    r'[' + re.escape(ASPAS_ABRE) + r']'
    r'([^' + re.escape(ASPAS_FECHA) + r'\n]{2,120})'
    r'[' + re.escape(ASPAS_FECHA) + r']'
)

# ---------------------------------------------------------------------------
# Ator
# ---------------------------------------------------------------------------
VERBOS_PT_EN = (
    r"escreveu|criou|atualizou|mencionou|alterou|mudou|adicionou|moveu|"
    r"comentou|atribuiu|created|changed|mentioned|posted|assigned|moved|"
    r"commented|replied|wrote|updated"
)
RE_ATOR_ASSUNTO = re.compile(
    r"^(.+?)\s+(?:" + VERBOS_PT_EN + r")\b",
    re.I,
)
RE_ATOR_CORPO = re.compile(
    r"^\s*([A-Z\u00C0-\u00DD][\w\u00C0-\u00FF.\- ]{1,40}?)\s+"
    r"(?:criou|atualizou|mencionou|alterou|mudou|comentou|adicionou|moveu|"
    r"created|changed|mentioned|posted|assigned|moved|commented|replied)",
    re.M,
)

# ---------------------------------------------------------------------------
# Tipo de notificacao (ordem = prioridade)
# ---------------------------------------------------------------------------
TIPO_REGRAS = [
    ("status", [
        r"status",
        r"movid[oa] para", r"moved to",
        r"label changed",
        r"opera\w* liquidada",
        r"liquidou a opera",
        r"conclu[i\u00ed]do", r"encerrad[oa]", r"finalizado",
    ]),
    ("prazo", [
        r"prazo", r"data de", r"vence", r"venceu",
        r"due date", r"overdue", r"timeline", r"date changed",
    ]),
    ("criada", [
        r"criou", r"criad", r"novo item", r"new item", r"new pulse",
        r"created", r"adicionou", r"added a new",
    ]),
    ("mencao", [
        r"mencionou", r"mentioned", r"atribuiu", r"assigned",
        r"marcou voc[e\u00ea]", r"tagged you",
    ]),
    ("atualizacao", [
        r"atualiza[c\u00e7]", r"atualizou", r"update", r"publicou",
        r"comentou", r"comment", r"respondeu", r"replied", r"reply",
        r"escreveu uma atualiza",
    ]),
]

# ---------------------------------------------------------------------------
# Valor de status
# ---------------------------------------------------------------------------
# Status comuns do Monday em PT/EN para captura em linha isolada
_STATUS_CONHECIDOS = (
    r"Conclu[i\u00ed]do|Done|Feito|Em [Aa]ndamento|Working on it|"
    r"Travado|Stuck|Parado|Criada?|Pendente|Liquidada?|"
    r"Aprovad[oa]|Rejeitad[oa]|Cancelad[oa]"
)

RE_STATUS_VALOR = [
    re.compile(r"status[^\n]{0,40}?(?:para|to|\u2192|->)\s*[\"']?([^\"'\n\.;]{1,40})", re.I),
    re.compile(r"(?:movid[oa] para|moved to)\s+[\"']?([^\"'\n\.;]{1,40})", re.I),
    # Linha isolada = valor do status
    re.compile(r"^(" + _STATUS_CONHECIDOS + r")\s*$", re.M),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
    # Encerramento definitivo tem prioridade absoluta sobre linha de status generica
    if re.search(r"liquidada?|liquidou a opera", texto, re.I):
        return "Liquidada"
    if re.search(r"conclu[i\u00ed]do|finalizado", texto, re.I):
        return "Concluido"
    if re.search(r"encerrad[oa]", texto, re.I):
        return "Encerrada"
    for regex in RE_STATUS_VALOR:
        m = regex.search(texto)
        if m:
            return m.group(1).strip(" '\".")
    return ""


def _item_nome(assunto, corpo):
    # 1) Padrao VERT: "... em NOME" no fim do assunto
    m = RE_NOME_ASSUNTO.search(assunto)
    if m:
        nome = m.group(1).strip()
        if nome and nome.lower() not in {"inbox", "a", "o", "um", "uma"}:
            return nome

    # 2) Texto entre aspas
    for fonte in (assunto, corpo):
        candidatos = list(RE_ASPAS.finditer(fonte))
        if not candidatos:
            continue
        for cm in candidatos:
            antes = fonte[max(0, cm.start() - 8):cm.start()].lower()
            if re.search(r"\b(em|no|na|in|on)\s*$", antes):
                return cm.group(1).strip()
        return max((cm.group(1).strip() for cm in candidatos), key=len)

    # 3) Assunto limpo como fallback
    limpo = re.sub(r"^(re:|fwd:|enc:)\s*", "", assunto, flags=re.I).strip()
    limpo = re.sub(r"\s*[-\u2013|]\s*monday\.com.*$", "", limpo, flags=re.I)
    limpo = re.sub(
        r"^.+?\s+(?:" + VERBOS_PT_EN + r")\s+\S+\s+em\s+",
        "", limpo, flags=re.I,
    )
    return limpo or "(sem titulo)"


def _ator(assunto, corpo, remetente_nome):
    m = RE_ATOR_ASSUNTO.search(assunto)
    if m:
        return m.group(1).strip()
    a = _primeiro(RE_ATOR_CORPO, corpo)
    if a:
        return a
    nome = re.sub(r"\s*via monday\.com\s*", "", remetente_nome or "", flags=re.I).strip()
    return nome or "(desconhecido)"


def _link(base):
    m = RE_LINK_MONDAY.search(base)
    if m:
        return m.group(0)
    m = RE_LINK_ANY.search(base)
    return m.group(0) if m else ""


def analisar(email_dict):
    """Recebe o dict de um email e devolve os campos Monday."""
    assunto = email_dict.get("assunto", "")
    corpo   = email_dict.get("corpo", "")
    base    = assunto + "\n" + corpo

    pulse_id  = _primeiro(RE_PULSE, base)
    board_id  = _primeiro(RE_BOARD, base)
    link      = _link(base)
    tipo      = _classificar(base)
    item_nome = _item_nome(assunto, corpo)
    ator      = _ator(assunto, corpo, email_dict.get("remetente_nome", ""))

    s_valor = ""
    if tipo == "status":
        s_valor = _status_valor(base)
        if not s_valor and re.search(r"opera\w* liquidada|liquidou a opera", base, re.I):
            s_valor = "Liquidada"
    elif tipo == "atualizacao":
        s_valor = _status_valor(base)

    chave = pulse_id or ("nome:" + re.sub(r"\s+", " ", item_nome.lower()).strip())

    return {
        "chave":        chave,
        "pulse_id":     pulse_id,
        "board_id":     board_id,
        "link":         link,
        "item_nome":    item_nome,
        "ator":         ator,
        "tipo":         tipo,
        "status_valor": s_valor,
    }
