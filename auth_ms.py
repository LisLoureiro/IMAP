"""Autenticação OAuth2 com a Microsoft (MSAL) via fluxo device-code.

O token (e o refresh token) ficam no cache do MSAL, que é persistido no
PostgreSQL — então o login sobrevive a reinícios do container.

Fluxo de uso:
    1. status_conta()        -> email conectado, ou None
    2. iniciar_device_flow() -> dict com a mensagem/código para o usuário
    3. concluir_device_flow(flow) -> conclui após o usuário autorizar no navegador
    4. token_silencioso()    -> access_token válido (renova sozinho), ou None
"""
import time

import msal

import db
from config import Config


def _app():
    cache = msal.SerializableTokenCache()
    salvo = db.carregar_cache()
    if salvo:
        cache.deserialize(salvo)
    app = msal.PublicClientApplication(
        Config.MS_CLIENT_ID, authority=Config.MS_AUTHORITY, token_cache=cache
    )
    return app, cache


def _persistir(cache):
    if cache.has_state_changed:
        db.salvar_cache(cache.serialize())


def configurado():
    return bool(Config.MS_CLIENT_ID)


def status_conta():
    if not configurado():
        return None
    app, _ = _app()
    contas = app.get_accounts()
    return contas[0]["username"] if contas else None


def token_silencioso():
    """Retorna um access_token válido usando o refresh token em cache, ou None."""
    if not configurado():
        return None
    app, cache = _app()
    contas = app.get_accounts()
    if not contas:
        return None
    res = app.acquire_token_silent(Config.MS_SCOPES, account=contas[0])
    _persistir(cache)
    return res.get("access_token") if res else None


def iniciar_device_flow():
    if not configurado():
        raise RuntimeError("Defina MS_CLIENT_ID (registro de app no Azure) primeiro.")
    app, _ = _app()
    flow = app.initiate_device_flow(scopes=Config.MS_SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(
            "Falha ao iniciar login: " + flow.get("error_description", "erro desconhecido")
        )
    return flow


def concluir_device_flow(flow, limite_seg=120):
    """Conclui o login após o usuário autorizar. Limita a espera para não travar."""
    app, cache = _app()
    flow = dict(flow)
    flow["expires_at"] = min(
        flow.get("expires_at", time.time() + limite_seg), time.time() + limite_seg
    )
    res = app.acquire_token_by_device_flow(flow)
    _persistir(cache)
    if "access_token" in res:
        return True
    raise RuntimeError(res.get("error_description", "Login não concluído."))


def desconectar():
    db.apagar_cache()


def xoauth2(email, token):
    """String SASL XOAUTH2 para o imaplib."""
    return f"user={email}\x01auth=Bearer {token}\x01\x01"
