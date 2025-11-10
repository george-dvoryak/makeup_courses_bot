#!/bin/bash
# Скрипт для запуска бота из Cursor IDE

# Переход в директорию проекта
cd "$(dirname "$0")"

# Проверка наличия виртуального окружения
if [ ! -d ".venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv .venv
fi

# Активация виртуального окружения
echo "Активация виртуального окружения..."
source .venv/bin/activate

# Проверка установки зависимостей
if ! python -c "import telebot" 2>/dev/null; then
    echo "Установка зависимостей..."
    pip install -r requirements.txt
fi

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo "⚠️  ВНИМАНИЕ: Файл .env не найден!"
    if [ -f ".env.example" ]; then
        echo "Создание .env из .env.example..."
        cp .env.example .env
        echo "⚠️  Пожалуйста, отредактируйте .env и заполните необходимые переменные!"
        exit 1
    else
        echo "❌ Файл .env.example также не найден!"
        exit 1
    fi
fi

# Запуск бота
echo "🚀 Запуск бота..."
python main.py

