"""Painel de acompanhamento de solicitações (notificações do Monday por email).

Rodar com:  streamlit run app.py
"""
import streamlit as st

import db
import email_client
import monday_parser
import auth_ms
from aggregacao import montar, cor_status
from config import Config

st.set_page_config(page_title="Solicitações", page_icon="§", layout="wide")
db.init_db()

# ---------------------------------------------------------------------------
# Estilo dos selos de status
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .selo { display:inline-block; padding:2px 10px; border-radius:999px;
              color:#fff; font-size:0.8rem; font-weight:600; white-space:nowrap; }
      .meta { color:#5d6678; font-size:0.86rem; }
      .item-titulo { font-size:1.05rem; font-weight:600; margin-bottom:2px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def selo(status):
    return f'<span class="selo" style="background:{cor_status(status)}">{status}</span>'


TIPO_ROTULO = {
    "criada": "Criada", "atualizacao": "Atualização", "status": "Mudança de status",
    "prazo": "Prazo/Data", "mencao": "Menção", "outro": "Outro",
}


def _eh_monday(remetente, corpo):
    alvo = Config.MONDAY_SENDER.lower().strip()
    if not alvo:
        return True
    return alvo in (remetente or "").lower() or "monday.com" in (corpo or "").lower()


def sincronizar(conexao, oauth_token=None):
    emails = email_client.buscar_emails(conexao=conexao, oauth_token=oauth_token)
    novas = ignoradas = 0
    for e in emails:
        if not _eh_monday(e["remetente"], e["corpo"]):
            ignoradas += 1
            continue
        registro = {**e, **monday_parser.analisar(e)}
        if db.inserir_se_nova(registro):
            novas += 1
    return novas, len(emails), ignoradas


# ---------------------------------------------------------------------------
# Barra lateral: conexão, sincronização e filtros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Conexão")
    host = st.text_input("Servidor IMAP", Config.IMAP_HOST)
    port = st.number_input("Porta", value=Config.IMAP_PORT, step=1)
    user = st.text_input("Email", Config.IMAP_USER)
    mailbox = st.text_input("Pasta", Config.IMAP_MAILBOX)

    st.subheader("Conta Microsoft (OAuth2)")
    if not auth_ms.configurado():
        st.warning("Defina MS_CLIENT_ID no .env (registro de app no Azure). Veja o README.")
    else:
        conta = auth_ms.status_conta()
        if conta:
            st.success(f"Conectado: {conta}")
            if st.button("Desconectar", use_container_width=True):
                auth_ms.desconectar()
                st.rerun()
        else:
            if st.button("Iniciar login Microsoft", use_container_width=True):
                try:
                    st.session_state["ms_flow"] = auth_ms.iniciar_device_flow()
                except RuntimeError as err:
                    st.error(str(err))
            flow = st.session_state.get("ms_flow")
            if flow:
                st.info(flow["message"])
                st.code(flow["user_code"])
                if st.button("Concluir login", type="primary", use_container_width=True):
                    try:
                        with st.spinner("Validando autorização…"):
                            auth_ms.concluir_device_flow(flow)
                        st.session_state.pop("ms_flow", None)
                        st.rerun()
                    except RuntimeError as err:
                        st.error(str(err))

    senha = ""
    with st.expander("Outro provedor (login por senha)"):
        senha = st.text_input("Senha (ou senha de app)", "", type="password")

    st.divider()
    if st.button("Sincronizar caixa", type="primary", use_container_width=True):
        token = auth_ms.token_silencioso()
        if not token and not senha:
            st.error("Conecte a conta Microsoft (ou use senha em 'Outro provedor').")
        else:
            conexao = {"host": host, "port": port, "user": user,
                       "password": senha, "mailbox": mailbox}
            try:
                with st.spinner("Buscando emails…"):
                    novas, total, ignoradas = sincronizar(conexao, oauth_token=token)
                st.success(f"{novas} nova(s) · {total} lidos · {ignoradas} não-Monday ignorados")
            except RuntimeError as err:
                st.error(str(err))

    st.divider()
    st.caption(f"{db.total_notificacoes()} notificações armazenadas")
    with st.expander("Apagar base local"):
        if st.button("Apagar tudo", use_container_width=True):
            db.limpar_tudo()
            st.rerun()

# ---------------------------------------------------------------------------
# Construção das solicitações
# ---------------------------------------------------------------------------
solicitacoes = montar(db.todas_notificacoes())

st.title("Solicitações")

if not solicitacoes:
    st.info(
        "Nenhuma solicitação ainda. Preencha a conexão na barra lateral e clique "
        "em **Sincronizar caixa** para puxar as notificações do Monday."
    )
    st.stop()

# Filtros
status_disp = sorted({s["status"] for s in solicitacoes})
col_f1, col_f2 = st.columns([2, 3])
with col_f1:
    filtro_status = st.multiselect("Status", status_disp, default=[])
with col_f2:
    busca = st.text_input("Buscar (nome, criador, status)", "").strip().lower()

filtradas = [
    s for s in solicitacoes
    if (not filtro_status or s["status"] in filtro_status)
    and (not busca or busca in s["item_nome"].lower()
         or busca in s["criador"].lower() or busca in s["status"].lower())
]

# Métricas por status
st.markdown("&nbsp;", unsafe_allow_html=True)
cols = st.columns(len(status_disp) + 1)
cols[0].metric("Total", len(solicitacoes))
contagem = {s: 0 for s in status_disp}
for s in solicitacoes:
    contagem[s["status"]] += 1
for col, stt in zip(cols[1:], status_disp):
    col.metric(stt, contagem[stt])

st.divider()
st.caption(f"{len(filtradas)} solicitação(ões)")

# ---------------------------------------------------------------------------
# Lista de solicitações
# ---------------------------------------------------------------------------
def fmt_data(iso):
    if not iso:
        return "—"
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


for s in filtradas:
    with st.container(border=True):
        topo = st.columns([6, 2])
        with topo[0]:
            st.markdown(f'<div class="item-titulo">{s["item_nome"]}</div>',
                        unsafe_allow_html=True)
            origem = "" if s["status_origem"] == "Monday" else " · status inferido"
            st.markdown(selo(s["status"]) + f'<span class="meta">{origem}</span>',
                        unsafe_allow_html=True)
        with topo[1]:
            if s["link"]:
                st.link_button("Abrir no Monday", s["link"], use_container_width=True)

        partes = [
            f"Criada por **{s['criador']}**",
            f"Última atividade: {fmt_data(s['ultima_atividade'])}",
            f"{s['n_eventos']} evento(s)",
        ]
        if s["prazo"]:
            partes.insert(1, f"Prazo: **{s['prazo']}**")
        st.markdown('<span class="meta">' + "  ·  ".join(partes) + "</span>",
                    unsafe_allow_html=True)

        with st.expander(f"Linha do tempo ({s['n_eventos']})"):
            for ev in s["timeline"]:
                rotulo = TIPO_ROTULO.get(ev["tipo"], ev["tipo"])
                extra = f" → {ev['status_valor']}" if ev["status_valor"] else ""
                st.markdown(
                    f"**{fmt_data(ev['data_email'])}** · {rotulo}{extra} · "
                    f"{ev['ator']}"
                )
                if ev["resumo"]:
                    st.caption(ev["resumo"])
