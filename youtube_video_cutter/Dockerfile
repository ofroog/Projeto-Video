FROM python:3.9-slim
# Instalar dependências do sistema para o Google Chrome


# Defina o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copie o arquivo requirements.txt para o contêiner
COPY requirements.txt .

# Instale as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copie o restante do código para o contêiner
COPY . .

# Defina a variável de ambiente PORT para o Flask usar
ENV PORT 8080

# Exponha a porta que o contêiner deve escutar
EXPOSE 8080

# Comando para rodar a aplicação Flask usando Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]

