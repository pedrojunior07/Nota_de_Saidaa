"""GET /api/health — usado pelo healthcheck do docker-compose e para ver,
no browser, que versão está a correr no servidor."""

import os

from flask import Blueprint, current_app, jsonify

bp = Blueprint("health", __name__)


@bp.route("/api/health")
def health():
    commit = os.environ.get("APP_GIT_COMMIT", "desconhecido")
    return jsonify({
        "status": "ok",
        "versao": os.environ.get("APP_VERSION", "dev"),
        "commit": commit[:8],
        "build": os.environ.get("APP_BUILD_DATE", "desconhecida"),
        "auth_mode": current_app.config.get("AUTH_MODE"),
    })
