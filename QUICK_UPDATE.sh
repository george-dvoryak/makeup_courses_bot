#!/bin/bash
# Быстрое обновление кода на PythonAnywhere
# Использование: скопируйте эти команды в Bash консоль на PythonAnywhere

echo "🔄 Обновление кода из репозитория..."

cd ~/makeup_courses_bot

echo "📥 Получение обновлений из Git..."
git pull

echo "📦 Проверка зависимостей..."
pip install --user -r requirements.txt

echo ""
echo "✅ Код обновлен!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Перейдите на вкладку Web"
echo "2. Нажмите кнопку Reload"
echo "3. Проверьте Error log"
echo "4. Протестируйте бота командой /start"
echo ""

