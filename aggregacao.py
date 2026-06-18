"""Monta as 'solicitações' a partir das notificações armazenadas.

Agrupa por `chave` (pulse_id do Monday). Para cada grupo calcula: nome do item,
quem criou, datas de criação e última atividade, nº de eventos, status atual
(último valor de status capturado; senão um estágio inferido) e a linha do tempo.
"""
import re
from datetime import datetime

from config import STATUS_COR, COR_NEUTRA

_GENERICOS = {"(sem título)", "nova atualização", "nova atualizacao", "(sem assunto)"}
RE_DATA = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")


def _dt(iso):
    try:
        return datetime.fromisoformat(iso) if iso else datetime.min
    except ValueError:
        return datetime.min


def _melhor_nome(eventos):
    candidatos = [e["item_nome"] for e in eventos
                  if e["item_nome"] and e["item_nome"].lower() not in _GENERICOS]
    if candidatos:
        # nome mais frequente; empate -> mais longo
        freq = {}
        for c in candidatos:
            freq[c] = freq.get(c, 0) + 1
        return sorted(candidatos, key=lambda c: (freq[c], len(c)), reverse=True)[0]
    return eventos[0]["item_nome"] or "(sem título)"


def _status_atual(eventos):
    """(status, origem). origem: 'Monday' (valor real) ou 'inferido'."""
    with_status = [e for e in eventos if e["tipo"] == "status" and e["status_valor"]]
    if with_status:
        ultimo = max(with_status, key=lambda e: _dt(e["data_email"]))
        return ultimo["status_valor"], "Monday"
    tipos = {e["tipo"] for e in eventos}
    if len(eventos) == 1 and "criada" in tipos:
        return "Criada", "inferido"
    # inatividade
    ultima = max(_dt(e["data_email"]) for e in eventos)
    if ultima != datetime.min and (datetime.now() - ultima).days > 30:
        return "Sem atividade recente", "inferido"
    return "Em andamento", "inferido"


def _criador(eventos):
    criadas = [e for e in eventos if e["tipo"] == "criada"]
    base = min(criadas or eventos, key=lambda e: _dt(e["data_email"]))
    return base["ator"] or "(desconhecido)"


def _prazo(eventos):
    for e in sorted(eventos, key=lambda e: _dt(e["data_email"]), reverse=True):
        if e["tipo"] == "prazo":
            m = RE_DATA.search(e["corpo"] or "") or RE_DATA.search(e["assunto"] or "")
            if m:
                return m.group(1)
    return ""


def cor_status(status):
    return STATUS_COR.get(status, COR_NEUTRA)


def montar(notificacoes):
    grupos = {}
    for n in notificacoes:
        grupos.setdefault(n["chave"], []).append(n)

    solicitacoes = []
    for chave, eventos in grupos.items():
        eventos_ord = sorted(eventos, key=lambda e: _dt(e["data_email"]), reverse=True)
        status, origem = _status_atual(eventos)
        link = next((e["link"] for e in eventos if e["link"]), "")
        solicitacoes.append({
            "chave": chave,
            "item_nome": _melhor_nome(eventos),
            "criador": _criador(eventos),
            "criada_em": min((e["data_email"] for e in eventos if e["data_email"]), default=""),
            "ultima_atividade": max((e["data_email"] for e in eventos if e["data_email"]), default=""),
            "n_eventos": len(eventos),
            "status": status,
            "status_origem": origem,
            "prazo": _prazo(eventos),
            "link": link,
            "timeline": eventos_ord,
        })

    solicitacoes.sort(key=lambda s: _dt(s["ultima_atividade"]), reverse=True)
    return solicitacoes
