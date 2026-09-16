"""Popula o MongoDB com os dados mínimos para a aplicação arrancar:

    - contas de demonstração (as mesmas de app/services/seed.py)
    - catálogo de módulos
    - documento único de configuração da instituição
    - contadores de numeração

Uso:
    python -m scripts.seed_mongo            # cria o que faltar
    python -m scripts.seed_mongo --forcar   # repõe as contas demo

Requer as variáveis MONGO_* no .env (ver .env.example).
"""

from __future__ import annotations

import argparse

from app.repositories.base import ensure_indexes, get_db
from app.repositories.modulos import ModuloRepository
from app.repositories.users import UserRepository
from app.services.seed import PASSWORD_PADRAO, USUARIOS_DEMO

CONFIG_INICIAL = {
    "_id": "instituicao",
    "nome_instituicao": "Standard Bank",
    "direcao": "Direção de Informática",
    "morada": "Av. 25 de Setembro, Maputo",
    "contacto": "+258 21 000 000",
    "email_contacto": None,
    "rodape_pdf": "Documento gerado eletronicamente — Nota de Saída de Equipamento",
    "origem_de": "Informática",
    "origem_local": "Sede IT",
    "local_emissao": "Maputo",
}


def semear(forcar: bool = False) -> None:
    db = get_db()
    ensure_indexes()

    users = UserRepository(db)
    existentes = [users.get_by_username(u) for u, _, _ in USUARIOS_DEMO]
    if all(existentes) and not forcar:
        print("Contas demo já existem. Use --forcar para repor. (Nada a fazer nas contas.)")
    else:
        for username, nome, perfil in USUARIOS_DEMO:
            nome = "Antonio Soto" if username == "A100001" else nome
            u = users.upsert_demo(
                nome=nome, username=username, perfil=perfil, password=PASSWORD_PADRAO
            )
            print(f"  utilizador  {u.username:<9} {u.perfil:<14} {u.nome}")

    modulos = ModuloRepository(db).semear_catalogo()
    print(f"  módulos     {', '.join(m['_id'] for m in modulos)}")

    db.configuracao.update_one(
        {"_id": "instituicao"}, {"$setOnInsert": CONFIG_INICIAL}, upsert=True
    )
    print("  configuração  _id=instituicao")

    print("\nContas demo: A100001 (admin) / A272754 (técnico) / A200550 (aprovador)")
    print(f"Palavra-passe: {PASSWORD_PADRAO}  (apenas AUTH_MODE=local)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed do MongoDB (Nota de Saída).")
    parser.add_argument("--forcar", action="store_true", help="repõe as contas demo")
    args = parser.parse_args()
    semear(forcar=args.forcar)
