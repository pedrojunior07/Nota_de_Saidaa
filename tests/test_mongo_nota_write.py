import os
from datetime import date

from app.repositories.base import get_db
from app.repositories.notas import MongoNotaRepository


def test_criar_nota_no_mongo():
    os.environ.setdefault("MONGO_URI", "mongodb://admin:admin123@localhost:27017/nota_saida?authSource=admin")
    os.environ.setdefault("MONGO_DB_NAME", "nota_saida")

    repo = MongoNotaRepository()
    numero = "REQ000006253074"

    doc = repo.criar(
        numero_referencia=numero,
        data_emissao=date.today(),
        funcionario="Maria Teste",
        email_funcionario="maria.teste@standardbank.co.mz",
        departamento="Infraestrutura",
        motivo="Teste de persistência Mongo",
        observacao="Registro de validação automática.",
        origem_local="Sede IT",
        local_emissao="Maputo",
        criado_por="A272754",
        itens=[
            {
                "tipo_item": "Laptop",
                "descricao": "Notebook de teste",
                "numero_serie": "SERIE-TESTE-1",
                "quantidade": 1,
            }
        ],
    )

    db = get_db()
    saved = db.notas_saida.find_one({"_id": doc["_id"]})

    try:
        assert saved is not None
        assert saved["numero_referencia"] == numero
        assert saved["funcionario"] == "Maria Teste"
        assert saved["estado"] == "rascunho"
        assert len(saved["itens"]) == 1
    finally:
        db.notas_saida.delete_one({"_id": doc["_id"]})


def test_ler_e_aprovar_nota_no_mongo():
    os.environ.setdefault("MONGO_URI", "mongodb://admin:admin123@localhost:27017/nota_saida?authSource=admin")
    os.environ.setdefault("MONGO_DB_NAME", "nota_saida")

    repo = MongoNotaRepository()
    numero = "REQ000006232676"

    doc = repo.criar(
        numero_referencia=numero,
        data_emissao=date.today(),
        funcionario="Carlos Revisão",
        email_funcionario="carlos.revisao@standardbank.co.mz",
        departamento="Segurança",
        motivo="Teste de leitura e aprovação Mongo",
        observacao="Validação de leitura/aprovação.",
        origem_local="Sede IT",
        local_emissao="Maputo",
        criado_por="A272754",
        itens=[
            {
                "tipo_item": "Monitor",
                "descricao": "Monitor de teste",
                "numero_serie": "SERIE-TESTE-2",
                "quantidade": 2,
            }
        ],
    )

    db = get_db()
    try:
        encontrado = repo.obter_por_id(doc["_id"])
        assert encontrado is not None
        assert encontrado["numero_referencia"] == numero

        repo.submeter_para_aprovacao(doc["_id"])
        repo.adicionar_historico(doc["_id"], "A272754", "Submeteu para aprovação")
        repo.aprovar(doc["_id"], comentario="Aprovado em teste", aprovado_por="A272754")

        final = repo.obter_por_id(doc["_id"])
        assert final["estado"] == "concluida"
        assert final["comentario_decisao"] == "Aprovado em teste"
        assert len(final["historico"]) == 1
        assert final["historico"][0]["acao"] == "Submeteu para aprovação"
    finally:
        db.notas_saida.delete_one({"_id": doc["_id"]})
