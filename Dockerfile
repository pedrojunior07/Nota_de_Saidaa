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

# Porta que a app vai expor
EXPOSE 5000

# Comando para iniciar a aplicação
CMD ["python", "run.py"]