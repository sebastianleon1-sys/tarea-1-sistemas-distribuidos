FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias primero (capa cacheada por Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Punto de entrada: simulación completa con ambas distribuciones
CMD ["python", "main.py", "--distribution", "both", "--queries", "10000", "--verbose"]