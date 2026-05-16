FROM python:3.11-slim

WORKDIR /app

# ffmpeg нужен обязательно
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY main.py .

# Каталог для временных файлов
RUN mkdir /app/temp

# Запуск бота
CMD ["python3", "main.py"]
