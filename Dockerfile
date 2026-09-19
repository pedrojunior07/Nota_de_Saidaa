# Imagem base com Python
FROM  nexus.standardbank.co.mz:7777/python:3.9

# Diretório de trabalho dentro do container
WORKDIR /app

# Copiar ficheiro de dependências primeiro (otimiza cache)
COPY requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Copiar o resto do código
COPY . .

# Script de entrypoint: aplica migrações da BD antes de arrancar a app
# (ver entrypoint.sh — corre em todos os arranques, seguro mesmo se a BD
# já estiver atualizada).
RUN chmod +x entrypoint.sh

# Porta que a app vai expor
EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
# Comando para iniciar a aplicação
CMD ["python", "run.py"]