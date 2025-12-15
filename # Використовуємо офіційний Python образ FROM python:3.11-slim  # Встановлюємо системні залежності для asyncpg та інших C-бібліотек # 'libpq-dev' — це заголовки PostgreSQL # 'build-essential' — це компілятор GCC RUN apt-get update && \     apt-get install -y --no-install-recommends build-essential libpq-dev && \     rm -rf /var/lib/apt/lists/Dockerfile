# Використовуємо офіційний Python образ
FROM python:3.11-slim

# Встановлюємо системні залежності для asyncpg та інших C-бібліотек
# 'libpq-dev' — це заголовки PostgreSQL
# 'build-essential' — це компілятор GCC
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо requirements.txt та встановлюємо Python-залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо решту коду
COPY . .

# Команда, яка запускає бота
# Нам потрібен Gunicorn (якщо це Web Service) або прямий запуск бота (якщо Worker)
# Оскільки бот містить aiohttp web-server (для Render), використовуємо цю команду:
CMD ["python", "bot.py"]
