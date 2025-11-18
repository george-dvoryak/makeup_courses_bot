#!/bin/bash
# Скрипт для синхронизации кода с PythonAnywhere
# Использование: скопируйте файлы с PythonAnywhere вручную или используйте этот скрипт как инструкцию

echo "Синхронизация кода с PythonAnywhere"
echo "===================================="
echo ""

echo "ВАРИАНТ 1: Через Git (рекомендуется)"
echo "-------------------------------------"
echo "На PythonAnywhere выполните:"
echo "  cd ~/makeup_courses_bot"
echo "  git status"
echo "  git add ."
echo "  git commit -m 'Working version'"
echo "  git push origin feature/remove-robocasa"
echo ""
echo "Затем локально:"
echo "  git pull origin feature/remove-robocasa"
echo ""

echo "ВАРИАНТ 2: Прямое копирование файлов"
echo "-------------------------------------"
echo "На PythonAnywhere выполните для каждого файла:"
echo "  cat ~/makeup_courses_bot/main.py > main.py.backup"
echo "  cat ~/makeup_courses_bot/webhook_app.py > webhook_app.py.backup"
echo "  # и т.д."
echo ""
echo "Затем скопируйте содержимое файлов локально"
echo ""

echo "ВАРИАНТ 3: Создать архив на PythonAnywhere"
echo "-------------------------------------------"
echo "На PythonAnywhere:"
echo "  cd ~/makeup_courses_bot"
echo "  tar -czf code_backup.tar.gz *.py *.txt *.md"
echo "  # Скачайте code_backup.tar.gz через Files tab"
echo ""

