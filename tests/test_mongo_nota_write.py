import os
from datetime import date

from app.repositories.base import get_db
from app.repositories.notas import MongoNotaRepository


def _dados_teste(numero, funcionario, email, departamento, motivo, observacao):
    return {
        "numero_referencia": numero,
        "data_emissao": date.today(),
        "funcionario": funcionario,
        "email_funcionario": email,
        "departamento": departamento,
        "motivo": motivo,
        "observacao": observacao,
        "origem_local": "Sede IT",
        "local_emissao": "Maputo",
    }


def test_criar_nota_no_mongo():
    os.environ.setdefault("MONGO_URI", "mongodb://admin:admin123@localhost:27017/nota_saida?authSource=admin")
    os.environ.setdefault("MONGO_DB_NAME", "nota_saida")

    repo = MongoNotaRepository()
    numero = "REQ000006253074"

    nota = repo.criar(
        _dados_teste(
            numero,
            "Maria Teste",
            "maria.teste@standardbank.co.mz",
            "Infraestrutura",
            "Teste de persistência Mongo",
            "Registro de validação automática.",
        ),
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
    saved = db.notas_saida.find_one({"_id": nota._oid})

    try:
        assert saved is not None
        assert saved["numero_referencia"] == numero
        assert saved["funcionario"] == "Maria Teste"
        assert saved["estado"] == "rascunho"
        assert len(saved["itens"]) == 1
    finally:
        db.notas_saida.delete_one({"_id": nota._oid})


def test_ler_e_aprovar_nota_no_mongo():
    os.environ.setdefault("MONGO_URI", "mongodb://admin:admin123@localhost:27017/nota_saida?authSource=admin")
    os.environ.setdefault("MONGO_DB_NAME", "nota_saida")

    repo = MongoNotaRepository()
    numero = "REQ000006232676"

    nota = repo.criar(
        _dados_teste(
            numero,
            "Carlos Revisão",
            "carlos.revisao@standardbank.co.mz",
            "Segurança",
            "Teste de leitura e aprovação Mongo",
            "Validação de leitura/aprovação.",
        ),
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
        encontrado = repo.obter_por_id(nota.id)
        assert encontrado is not None
        assert encontrado.numero_referencia == numero

        repo.submeter(nota.id)
        repo.adicionar_historico(nota.id, "A272754", "Submeteu para aprovação")
        repo.aprovar(nota.id, comentario="Aprovado em teste", aprovado_por="A272754")

        # A aprovação é o penúltimo passo: fica "aprovada", a aguardar a
        # assinatura de «Recebido» para só então concluir (fluxo corrigido —
        # antes saltava logo para "concluida" ao aprovar, o que era um bug).
        aprovada = repo.obter_por_id(nota.id)
        assert aprovada.estado == "aprovada"
        assert aprovada.comentario_decisao == "Aprovado em teste"
        assert len(aprovada.historico) == 1
        assert aprovada.historico[0].acao == "Submeteu para aprovação"
    finally:
        db.notas_saida.delete_one({"_id": nota._oid})
