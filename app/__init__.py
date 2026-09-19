"""Factory da aplicação Flask."""

import os

from flask import Flask, render_template
from flask_login import current_user

from config import config_by_name
from app.extensions import csrf, db, login_manager, migrate
from app.utils.filters import estado_badge, estado_label, formatar_data, perfil_label


def create_app(config_name="development"):
    app = Flask(__name__, instance_relative_config=True)
    config_class = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["PDF_FOLDER"], exist_ok=True)
    # garantir pasta de assinaturas
    try:
        os.makedirs(app.config.get("SIGNATURE_FOLDER"), exist_ok=True)
    except Exception:
        pass

    _registar_extensoes(app)
    _garantir_migracoes(app)
    # Aplicar correções rápidas de esquema para SQLite (colunas de assinatura)
    _garantir_colunas_assinatura_sqlite(app)
    _garantir_tabelas_novas(app)
    _registar_blueprints(app)
    _registar_contexto(app)
    _registar_erros(app)
    _registar_comandos(app)
    _garantir_dados_iniciais(app)

    return app


def _registar_extensoes(app):
    db.init_app(app)
    from app.models import (  # noqa: F401
        CampoDinamico,
        Configuracao,
        Historico,
        HistoricoEntrega,
        ItemEntrega,
        ItemNota,
        NotaEntrega,
        NotaSaida,
        User,
        ValorCampoDinamico,
    )
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            if os.environ.get("USE_MONGO_USERS", "0").strip().lower() in {"1", "true", "yes", "on"}:
                from app.repositories.users import UserRepository
                return UserRepository().get(user_id)
            return db.session.get(User, int(user_id))
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            return None

    @login_manager.unauthorized_handler
    def nao_autorizado():
        from flask import flash, redirect, request, url_for

        flash("Por favor, inicie sessão para aceder a esta página.", "warning")
        return redirect(url_for("auth.login", next=request.path))


def _registar_blueprints(app):
    from app.routes.admin import bp as admin_bp
    from app.routes.aprovacoes import bp as aprovacoes_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.entrega import bp as entrega_bp
    from app.routes.modulos import bp as modulos_bp
    from app.routes.notas import bp as notas_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(modulos_bp)
    app.register_blueprint(notas_bp)
    app.register_blueprint(aprovacoes_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(entrega_bp)

    _registar_guarda_modulo(app)


def _registar_guarda_modulo(app):
    """Só deixa aceder às rotas de um módulo depois de o utilizador o escolher."""
    from flask import redirect, request, session, url_for

    from app.routes.modulos import BLUEPRINT_PARA_MODULO

    # As imagens de assinatura são um recurso partilhado (mesma pasta,
    # mesmas regras de acesso) independentemente de quem gerou o URL.
    # url_assinatura() aponta sempre para "notas.servir_assinatura" —
    # sem esta isenção, um utilizador a trabalhar no módulo "entrega"
    # nunca conseguia ver nenhuma assinatura (o pedido à imagem era
    # redirecionado para /modulos, e o <img> ficava partido).
    _ENDPOINTS_ISENTOS_DE_MODULO = {"notas.servir_assinatura", "entrega.servir_assinatura"}

    @app.before_request
    def _exigir_modulo():
        if not current_user.is_authenticated:
            return None
        if request.endpoint in _ENDPOINTS_ISENTOS_DE_MODULO:
            return None
        modulos_da_rota = BLUEPRINT_PARA_MODULO.get(request.blueprint)
        if not modulos_da_rota:
            return None  # auth, modulos, static, páginas de erro…
        if session.get("modulo") not in modulos_da_rota:
            if current_user.is_admin():
                # Administrador gere a plataforma num único módulo implícito
                # — nunca escolhe nem troca, e nunca acede às notas.
                session["modulo"] = "saida"
                return None
            return redirect(url_for("modulos.escolher"))
        return None


def _registar_contexto(app):
    app.jinja_env.filters["estado_label"] = estado_label
    app.jinja_env.filters["estado_badge"] = estado_badge
    app.jinja_env.filters["perfil_label"] = perfil_label
    app.jinja_env.filters["formatar_data"] = formatar_data

    _versao_assets = {}

    @app.template_global()
    def asset(filename):
        """url_for('static', ...) com ?v=<mtime> para o browser não servir CSS/JS em cache."""
        from flask import url_for

        versao = _versao_assets.get(filename)
        if versao is None or app.debug:
            try:
                versao = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
            except OSError:
                versao = 0
            _versao_assets[filename] = versao
        return url_for("static", filename=filename, v=versao)

    @app.context_processor
    def injectar_globais():
        from flask import session

        from app.models.configuracao import Configuracao
        from app.routes.modulos import MODULOS
        from app.utils.constants import ESTADOS_LABEL, PERFIS_LABEL

        config = None
        try:
            config = db.session.get(Configuracao, 1)
        except Exception:
            config = None
        from app.utils.assinatura import url_assinatura
        from app.utils.assinatura_zonas import (
            CAMPOS_ASSINATURA,
            CAMPOS_ASSINATURA_ENTREGA,
            DEFAULTS_ASSINATURA,
            DEFAULTS_ASSINATURA_ENTREGA,
            LINHA_LARGURA,
            LINHA_LARGURA_ENTREGA,
            ZONAS_ASSINATURA,
        )

        modulo_ativo = session.get("modulo")
        return {
            "current_user": current_user,
            "config_instituicao": config,
            "ESTADOS_LABEL": ESTADOS_LABEL,
            "PERFIS_LABEL": PERFIS_LABEL,
            "app_name": app.config.get("APP_NAME", "Nota de Saída"),
            "url_assinatura": url_assinatura,
            "ASSINATURA_DEFAULTS": DEFAULTS_ASSINATURA,
            "ASSINATURA_ZONAS": ZONAS_ASSINATURA,
            "ASSINATURA_CAMPOS": CAMPOS_ASSINATURA,
            "ASSINATURA_LINHA_LARGURA": LINHA_LARGURA,
            "ASSINATURA_CAMPOS_ENTREGA": CAMPOS_ASSINATURA_ENTREGA,
            "ASSINATURA_DEFAULTS_ENTREGA": DEFAULTS_ASSINATURA_ENTREGA,
            "ASSINATURA_LINHA_LARGURA_ENTREGA": LINHA_LARGURA_ENTREGA,
            "modulo_ativo": modulo_ativo,
            "modulo_info": MODULOS.get(modulo_ativo),
        }


def _registar_erros(app):
    @app.errorhandler(403)
    def erro_403(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def erro_404(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def erro_500(_e):
        return render_template("errors/500.html"), 500


def _registar_comandos(app):
    @app.cli.command("seed")
    def comando_seed():
        """Popula a base de dados com utilizadores e notas de demonstração."""
        from app.services.seed import executar_seed

        criado = executar_seed(forcar=False)
        if criado:
            print("Dados iniciais criados com sucesso.")
            print("Contas: admin / tecnico / aprovador @standardbank.co.mz")
            print("Palavra-passe: Standard@2026")
        else:
            print("A base de dados já contém utilizadores. Nada a fazer.")


def _garantir_migracoes(app):
    """Cria as tabelas e corrige esquemas legados, incluindo o campo username."""
    from sqlalchemy import inspect

    with app.app_context():
        try:
            inspector = inspect(db.engine)
            if inspector.has_table("users"):
                colunas = {col["name"] for col in inspector.get_columns("users")}
                if "username" in colunas:
                    return

            from flask_migrate import upgrade

            upgrade()
        except Exception:
            try:
                app.logger.exception("Falha ao aplicar migrações da base de dados")
            except Exception:
                pass
            try:
                db.session.rollback()
            except Exception:
                pass


def _garantir_tabelas_novas(app):
    """Cria tabelas de modelos novos que ainda não existam (ex.: Nota de Entrega).

    `create_all` só cria o que falta — não altera tabelas existentes. Em produção
    o Alembic continua a ser a fonte da verdade.
    """
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass


def _garantir_dados_iniciais(app):
    """Após flask db upgrade, a primeira execução cria contas e notas de exemplo."""
    from sqlalchemy import inspect

    with app.app_context():
        try:
            if not inspect(db.engine).has_table("users"):
                return
            from app.services.seed import executar_seed

            executar_seed(forcar=False)
        except Exception:
            db.session.rollback()


def _garantir_colunas_assinatura_sqlite(app):
    """Se a app usa SQLite, adiciona colunas faltantes necessárias para assinaturas.

    Esta é uma correção pragmática para desenvolvimento local quando as migrações
    ainda não foram aplicadas. Não substitui o uso de Alembic em produção.
    """
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if not uri.startswith("sqlite"):
        return

    # extrair caminho do ficheiro sqlite (sqlite:///C:/path/to/db)
    db_path = uri.replace("sqlite:///", "")
    # normalizar separadores
    db_path = db_path.replace("/", os.sep)
    if not os.path.exists(db_path):
        return

    try:
        import sqlite3

        con = sqlite3.connect(db_path)
        cur = con.cursor()

        def has_table(table):
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            return cur.fetchone() is not None

        def has_column(table, column):
            if not has_table(table):
                return True
            cur.execute(f"PRAGMA table_info('{table}')")
            cols = [row[1] for row in cur.fetchall()]
            return column in cols

        changes = []

        if not has_column("users", "username"):
            cur.execute("ALTER TABLE users ADD COLUMN username VARCHAR(20)")
            rows = cur.execute(
                "SELECT id, email FROM users WHERE username IS NULL OR username = ''"
            ).fetchall()
            for user_id, email in rows:
                base = (email or "").split("@", 1)[0].upper().strip()
                if not base or not base.replace("-", "").replace("_", "").isalnum():
                    base = f"A{int(user_id):06d}"
                cur.execute("UPDATE users SET username = ? WHERE id = ?", (base, user_id))
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users(username)"
            )
            changes.append("users.username")

        if not has_column("users", "assinatura_path"):
            cur.execute("ALTER TABLE users ADD COLUMN assinatura_path VARCHAR(255)")
            changes.append("users.assinatura_path")

        if not has_column("users", "assinatura_reutilizavel"):
            cur.execute(
                "ALTER TABLE users ADD COLUMN assinatura_reutilizavel BOOLEAN NOT NULL DEFAULT 0"
            )
            changes.append("users.assinatura_reutilizavel")

        if not has_column("notas_saida", "assinatura_entregue_path"):
            cur.execute(
                "ALTER TABLE notas_saida ADD COLUMN assinatura_entregue_path VARCHAR(255)"
            )
            changes.append("notas_saida.assinatura_entregue_path")

        if not has_column("notas_saida", "assinatura_aprovador_path"):
            cur.execute(
                "ALTER TABLE notas_saida ADD COLUMN assinatura_aprovador_path VARCHAR(255)"
            )
            changes.append("notas_saida.assinatura_aprovador_path")

        if not has_column("notas_saida", "revisao_tecnico_id"):
            cur.execute("ALTER TABLE notas_saida ADD COLUMN revisao_tecnico_id INTEGER")
            changes.append("notas_saida.revisao_tecnico_id")

        # adicionar colunas de posição/escala (x,y,w,h) para ambas assinaturas
        for col in (
            'assinatura_entregue_x','assinatura_entregue_y','assinatura_entregue_w','assinatura_entregue_h',
            'assinatura_aprovador_x','assinatura_aprovador_y','assinatura_aprovador_w','assinatura_aprovador_h',
        ):
            if not has_column('notas_saida', col):
                cur.execute(f"ALTER TABLE notas_saida ADD COLUMN {col} FLOAT")
                changes.append(f"notas_saida.{col}")

        if changes:
            con.commit()
            try:
                app.logger.info("Applied sqlite schema changes: %s", ", ".join(changes))
            except Exception:
                pass

        con.close()
    except Exception:
        # Não queremos bloquear o arranque da aplicação por uma tentativa de alteração de esquema
        try:
            app.logger.exception("Falha ao aplicar alterações sqlite de schema de assinaturas")
        except Exception:
            pass

