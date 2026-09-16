import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'nota_saida.db')
print('Using DB:', DB)
if not os.path.exists(DB):
    print('Database file not found:', DB)
    raise SystemExit(1)

con = sqlite3.connect(DB)
cur = con.cursor()

# Helper to check column
def has_column(table, column):
    cur.execute(f"PRAGMA table_info('{table}')")
    cols = [row[1] for row in cur.fetchall()]
    return column in cols

changes = []

# users.assinatura_path
if not has_column('users', 'assinatura_path'):
    cur.execute("ALTER TABLE users ADD COLUMN assinatura_path VARCHAR(255)")
    changes.append('users.assinatura_path')

# users.assinatura_reutilizavel
if not has_column('users', 'assinatura_reutilizavel'):
    cur.execute("ALTER TABLE users ADD COLUMN assinatura_reutilizavel BOOLEAN NOT NULL DEFAULT 0")
    changes.append('users.assinatura_reutilizavel')

# notas_saida.assinatura_entregue_path
if not has_column('notas_saida', 'assinatura_entregue_path'):
    cur.execute("ALTER TABLE notas_saida ADD COLUMN assinatura_entregue_path VARCHAR(255)")
    changes.append('notas_saida.assinatura_entregue_path')

# notas_saida.assinatura_aprovador_path
if not has_column('notas_saida', 'assinatura_aprovador_path'):
    cur.execute("ALTER TABLE notas_saida ADD COLUMN assinatura_aprovador_path VARCHAR(255)")
    changes.append('notas_saida.assinatura_aprovador_path')

if not has_column('notas_saida', 'revisao_tecnico_id'):
    cur.execute("ALTER TABLE notas_saida ADD COLUMN revisao_tecnico_id INTEGER")
    changes.append('notas_saida.revisao_tecnico_id')

if changes:
    con.commit()
    print('Added columns:', ', '.join(changes))
else:
    print('No changes required; columns already present.')

con.close()
