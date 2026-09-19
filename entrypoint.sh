#!/bin/sh
# Corre sempre que o container arranca (dev, staging e produção): aplica
# quaisquer migrações da base de dados que ainda não tenham sido aplicadas
# ao volume persistente (/app/instance), e só depois inicia a aplicação.
# Se a base de dados já estiver atualizada, "flask db upgrade" não faz
# nada — é seguro correr em todos os arranques.
set -e

echo "[entrypoint] A aplicar migrações da base de dados..."
python -m flask db upgrade

echo "[entrypoint] A iniciar a aplicação..."
exec "$@"
