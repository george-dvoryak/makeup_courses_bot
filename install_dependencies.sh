#!/bin/bash
# Скрипт для установки зависимостей на PythonAnywhere

echo "============================================================"
echo "УСТАНОВКА ЗАВИСИМОСТЕЙ НА PYTHONANYWHERE"
echo "============================================================"

# Переходим в директорию проекта
cd ~/makeup_courses_bot || exit 1

echo ""
echo "1. Проверка requirements.txt..."
if [ ! -f requirements.txt ]; then
    echo "❌ Файл requirements.txt не найден!"
    exit 1
fi
echo "✅ requirements.txt найден"

echo ""
echo "2. Установка зависимостей..."
echo "Используется: pip3.10 install --user -r requirements.txt"
echo ""

pip3.10 install --user -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Зависимости установлены успешно!"
else
    echo ""
    echo "❌ Ошибка при установке зависимостей"
    exit 1
fi

echo ""
echo "3. Проверка установки основных модулей..."
python3.10 -c "import telebot; print('✅ telebot установлен')" 2>/dev/null || echo "❌ telebot не установлен"
python3.10 -c "import flask; print('✅ flask установлен')" 2>/dev/null || echo "❌ flask не установлен"
python3.10 -c "import requests; print('✅ requests установлен')" 2>/dev/null || echo "❌ requests не установлен"

echo ""
echo "============================================================"
echo "УСТАНОВКА ЗАВЕРШЕНА"
echo "============================================================"
echo ""
echo "Теперь запустите: python3.10 diagnose_webhook.py"

