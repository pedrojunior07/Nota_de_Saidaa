"""Parâmetros institucionais editáveis pelo administrador."""

from app.extensions import db


class Configuracao(db.Model):
    """Configuração singleton da instituição (id=1)."""

    __tablename__ = "configuracoes"

    id = db.Column(db.Integer, primary_key=True)
    nome_instituicao = db.Column(db.String(200), nullable=False, default="Standard Bank")
    direcao = db.Column(db.String(200), nullable=False, default="Direção de Informática")
    morada = db.Column(db.String(255), nullable=True)
    contacto = db.Column(db.String(80), nullable=True)
    email_contacto = db.Column(db.String(150), nullable=True)
    rodape_pdf = db.Column(
        db.String(255),
        nullable=True,
        default="Documento gerado eletronicamente — Nota de Saída de Equipamento",
    )
    origem_de = db.Column(db.String(80), nullable=False, default="Informática", server_default="Informática")
    origem_local = db.Column(db.String(120), nullable=False, default="Sede IT", server_default="Sede IT")
    local_emissao = db.Column(db.String(80), nullable=False, default="Maputo", server_default="Maputo")

    @classmethod
    def obter(cls):
        """Devolve a configuração existente ou cria a predefinida."""
        config = db.session.get(cls, 1)
        if config is None:
            config = cls(id=1)
            db.session.add(config)
            db.session.commit()
        return config
