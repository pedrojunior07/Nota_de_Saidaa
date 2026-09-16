"""Configuração e verificação da conexão com MongoDB."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


class MongoConnectionError(RuntimeError):
    """Erro amigável quando o MongoDB não está acessível."""


@dataclass(frozen=True)
class MongoConfig:
    """Configuração do MongoDB carregada exclusivamente de variáveis de ambiente."""

    uri: str
    database_name: str

    @classmethod
    def from_env(cls):
        load_dotenv()

        uri = (os.environ.get("MONGO_URI") or "").strip()
        database_name = (os.environ.get("MONGO_DB_NAME") or "").strip()

        missing = [
            name
            for name, value in (
                ("MONGO_URI", uri),
                ("MONGO_DB_NAME", database_name),
            )
            if not value
        ]
        if missing:
            raise MongoConnectionError(
                "Variáveis MongoDB em falta: " + ", ".join(missing)
            )

        return cls(uri=uri, database_name=database_name)


class MongoConnection:
    """Cliente MongoDB com uma operação explícita de teste de conexão."""

    def __init__(self, config=None):
        self.config = config or MongoConfig.from_env()
        self.client = MongoClient(self.config.uri, serverSelectionTimeoutMS=5000)

    def ping(self):
        """Confirma que o servidor está acessível e autenticando corretamente."""
        try:
            self.client.admin.command("ping")
            return True
        except PyMongoError as exc:
            raise MongoConnectionError(
                "Não foi possível conectar ao MongoDB. "
                "Confirme se o container está em execução e se as credenciais estão corretas."
            ) from exc

    def database(self):
        """Obtém a base configurada; o MongoDB cria-a quando houver uma escrita."""
        return self.client[self.config.database_name]

    def close(self):
        self.client.close()


def test_mongo_connection():
    """Testa a conexão e devolve uma mensagem adequada para scripts/CLI."""
    connection = None
    try:
        connection = MongoConnection()
        connection.ping()
        return f"Conexão com MongoDB OK: {connection.config.database_name}"
    except MongoConnectionError as exc:
        return f"Falha na conexão com MongoDB: {exc}"
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    print(test_mongo_connection())