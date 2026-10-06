"""Cópia de segurança automática das notas concluídas (OneDrive / SharePoint /
pasta partilhada).

Quando uma nota é concluída (assinatura «Recebido»), o PDF final é enviado
para o destino configurado — sem intervenção de ninguém.

    BACKUP_MODE = "desligado"  -> não faz nada (omissão)
    BACKUP_MODE = "webhook"    -> envia o PDF para um flow do Power Automate
                                  (gatilho "When an HTTP request is received"),
                                  que o grava no OneDrive/SharePoint.
                                  BACKUP_WEBHOOK_URL = URL do gatilho do flow.
    BACKUP_MODE = "pasta"      -> copia o PDF para uma pasta (ex.: share de rede
                                  montado no container). BACKUP_PASTA = caminho.

Organização no destino:  Notas de Saída/2026/10/NS_000012-2026_REQ..._Nome.pdf

Regras de robustez (como nas notificações):
  - nunca levanta exceções para quem chama: a nota conclui-se mesmo que a
    cópia falhe; as falhas ficam no log (WARNING);
  - corre numa thread com 3 tentativas, para não atrasar o técnico;
  - `flask backup-notas` reenvia as notas concluídas (retry ou carga inicial).

Guia de configuração: docs/backup_onedrive.md
"""

from __future__ import annotations

import base64
import logging
import os
import re
import shutil
import threading
import time
import unicodedata

log = logging.getLogger(__name__)

_TIPOS = {
    "saida": {"pasta": "Notas de Saída", "prefixo": "NS"},
    "entrega": {"pasta": "Notas de Entrega", "prefixo": "NE"},
}


def _cfg(chave, omissao=""):
    from flask import current_app

    return current_app.config.get(chave, os.environ.get(chave, omissao))


def modo() -> str:
    return (str(_cfg("BACKUP_MODE", "desligado")) or "desligado").strip().lower()


def _seguro_para_ficheiro(texto: str) -> str:
    """Remove acentos e caracteres que o OneDrive/Windows não aceitam."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", texto)
    return re.sub(r"\s+", "-", texto.strip())[:60] or "sem-nome"


def preparar(tipo: str, nota) -> dict | None:
    """Recolhe tudo o que é preciso (ainda dentro do pedido): caminhos, nomes,
    metadados e o próprio PDF. Devolve None se a nota não tiver PDF."""
    pdf = getattr(nota, "pdf_path", None)
    if not pdf or not os.path.isfile(pdf):
        log.warning("Backup: nota %s sem PDF em disco (%s) — não enviada.", getattr(nota, "id", "?"), pdf)
        return None
    info = _TIPOS[tipo]
    numero = getattr(nota, "numero_documento", None) or str(nota.id)
    concluida = getattr(nota, "data_conclusao", None)
    ano, mes = (concluida.year, concluida.month) if concluida else (time.localtime().tm_year, time.localtime().tm_mon)
    nome = "_".join(filter(None, [
        info["prefixo"],
        numero.replace("/", "-"),
        _seguro_para_ficheiro(getattr(nota, "numero_referencia", "") or ""),
        _seguro_para_ficheiro(getattr(nota, "funcionario", "") or ""),
    ])) + ".pdf"
    criador = getattr(nota, "criador", None)
    return {
        "pasta": f"{info['pasta']}/{ano}/{mes:02d}",
        "nome_ficheiro": nome,
        "caminho_pdf": pdf,
        "tipo": tipo,
        "numero": numero,
        "referencia": getattr(nota, "numero_referencia", "") or "",
        "colaborador": getattr(nota, "funcionario", "") or "",
        "email_colaborador": getattr(nota, "email_funcionario", "") or "",
        "departamento": getattr(nota, "departamento", "") or "",
        "tecnico": (getattr(criador, "nome_exibicao", None) or getattr(criador, "nome", None) or "") if criador else "",
        "data_conclusao": concluida.isoformat() if concluida else "",
    }


def _enviar(dados: dict, cfg: dict) -> None:
    """Envia uma nota (síncrono). Levanta exceção se falhar."""
    if cfg["modo"] == "pasta":
        if not cfg["pasta"]:
            raise RuntimeError("BACKUP_PASTA não definido.")
        destino = os.path.join(cfg["pasta"], *dados["pasta"].split("/"))
        os.makedirs(destino, exist_ok=True)
        shutil.copy2(dados["caminho_pdf"], os.path.join(destino, dados["nome_ficheiro"]))
        return
    if cfg["modo"] == "webhook":
        import requests

        if not cfg["url"]:
            raise RuntimeError("BACKUP_WEBHOOK_URL não definido.")
        with open(dados["caminho_pdf"], "rb") as fh:
            conteudo = base64.b64encode(fh.read()).decode()
        corpo = {k: v for k, v in dados.items() if k != "caminho_pdf"}
        corpo["conteudo_base64"] = conteudo
        resp = requests.post(cfg["url"], json=corpo, timeout=cfg["timeout"])
        if resp.status_code >= 300:
            raise RuntimeError(f"o flow respondeu {resp.status_code}: {resp.text[:200]}")
        return
    raise RuntimeError(f"BACKUP_MODE desconhecido: {cfg['modo']}")


def _config_atual() -> dict:
    return {
        "modo": modo(),
        "url": str(_cfg("BACKUP_WEBHOOK_URL", "") or "").strip(),
        "pasta": str(_cfg("BACKUP_PASTA", "") or "").strip(),
        "timeout": float(_cfg("BACKUP_TIMEOUT", 60) or 60),
    }


def enviar_agora(tipo: str, nota) -> tuple[bool, str]:
    """Envio síncrono (usado pelo comando `flask backup-notas`)."""
    cfg = _config_atual()
    if cfg["modo"] == "desligado":
        return False, "BACKUP_MODE=desligado"
    dados = preparar(tipo, nota)
    if dados is None:
        return False, "sem PDF"
    try:
        _enviar(dados, cfg)
        return True, f"{dados['pasta']}/{dados['nome_ficheiro']}"
    except Exception as erro:  # noqa: BLE001
        return False, str(erro)


def guardar_nota_concluida(tipo: str, nota) -> None:
    """Chamado quando a nota é concluída. Não bloqueia e nunca falha."""
    try:
        cfg = _config_atual()
        if cfg["modo"] == "desligado":
            return
        dados = preparar(tipo, nota)
        if dados is None:
            return
    except Exception:  # noqa: BLE001
        log.exception("Backup: falha ao preparar a nota %s.", getattr(nota, "id", "?"))
        return

    def _trabalho():
        for tentativa in range(1, 4):
            try:
                _enviar(dados, cfg)
                log.warning("Backup OK (%s): %s/%s", cfg["modo"], dados["pasta"], dados["nome_ficheiro"])
                return
            except Exception as erro:  # noqa: BLE001
                log.warning("Backup falhou (tentativa %s/3) para %s: %s", tentativa, dados["nome_ficheiro"], erro)
                time.sleep(5 * tentativa)
        log.warning("Backup DESISTIU de %s — reenviar com `flask backup-notas`.", dados["nome_ficheiro"])

    threading.Thread(target=_trabalho, name=f"backup-{dados['numero']}", daemon=True).start()
