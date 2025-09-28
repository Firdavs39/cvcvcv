# =============================================================================
# СКРИПТ УСТАНОВКИ AI-АГЕНТА ФИРДАВСА ФАЙЗУЛЛАЕВА
# Профессиональная установка с mem0 и Gemini интеграцией
# =============================================================================

Write-Host "🤖 Установка AI-агента Фирдавса Файзуллаева" -ForegroundColor Cyan
Write-Host "=" -repeat 60 -ForegroundColor Cyan

# Проверка версии Python
Write-Host "🔍 Проверка Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python 3\.([8-9]|1[0-9])") {
        Write-Host "✅ Python обнаружен: $pythonVersion" -ForegroundColor Green
    } else {
        Write-Host "❌ Требуется Python 3.8+ Текущая версия: $pythonVersion" -ForegroundColor Red
        Write-Host "📥 Скачайте Python с https://python.org" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ Python не найден в PATH" -ForegroundColor Red
    Write-Host "📥 Установите Python с https://python.org" -ForegroundColor Yellow
    exit 1
}

# Создание виртуального окружения
Write-Host "🏗️  Создание виртуального окружения..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "📂 Виртуальное окружение уже существует" -ForegroundColor Green
} else {
    python -m venv venv
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Виртуальное окружение создано" -ForegroundColor Green
    } else {
        Write-Host "❌ Ошибка создания виртуального окружения" -ForegroundColor Red
        exit 1
    }
}

# Активация виртуального окружения
Write-Host "🔧 Активация виртуального окружения..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Виртуальное окружение активировано" -ForegroundColor Green
} else {
    Write-Host "❌ Ошибка активации виртуального окружения" -ForegroundColor Red
    exit 1
}

# Обновление pip
Write-Host "📦 Обновление pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Установка зависимостей
Write-Host "📚 Установка зависимостей..." -ForegroundColor Yellow
Write-Host "   Это может занять несколько минут..." -ForegroundColor Gray

pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Все зависимости установлены" -ForegroundColor Green
} else {
    Write-Host "❌ Ошибка установки зависимостей" -ForegroundColor Red
    Write-Host "🔄 Попробуйте: pip install -r requirements.txt --no-cache-dir" -ForegroundColor Yellow
    exit 1
}

# Проверка файла .env
Write-Host "🔑 Проверка конфигурации..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "✅ Файл .env найден" -ForegroundColor Green
    
    # Проверка ключевых переменных
    $envContent = Get-Content ".env" -Raw
    $hasToken = $envContent -match "TELEGRAM_TOKEN=.+"
    $hasGemini = $envContent -match "GEMINI_API_KEY=.+"
    
    if ($hasToken -and $hasGemini) {
        Write-Host "✅ Основные API ключи настроены" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Проверьте настройки в .env файле:" -ForegroundColor Yellow
        if (!$hasToken) { Write-Host "   - TELEGRAM_TOKEN не настроен" -ForegroundColor Red }
        if (!$hasGemini) { Write-Host "   - GEMINI_API_KEY не настроен" -ForegroundColor Red }
    }
    
    $hasOpenAI = $envContent -match "OPENAI_API_KEY=.+"
    if (!$hasOpenAI) {
        Write-Host "⚠️  OPENAI_API_KEY не настроен - mem0 будет в ограниченном режиме" -ForegroundColor Yellow
        Write-Host "   Для полной функциональности добавьте OpenAI ключ в .env" -ForegroundColor Gray
    }
} else {
    Write-Host "❌ Файл .env не найден!" -ForegroundColor Red
    Write-Host "📝 Создайте .env файл со следующими переменными:" -ForegroundColor Yellow
    Write-Host "TELEGRAM_TOKEN=ваш_telegram_token" -ForegroundColor Gray
    Write-Host "GEMINI_API_KEY=ваш_gemini_key" -ForegroundColor Gray
    Write-Host "OPENAI_API_KEY=ваш_openai_key" -ForegroundColor Gray
    exit 1
}

# Создание необходимых директорий
Write-Host "📁 Создание директорий..." -ForegroundColor Yellow
$directories = @("memory_db", "logs")
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir
        Write-Host "✅ Создана директория: $dir" -ForegroundColor Green
    } else {
        Write-Host "📂 Директория уже существует: $dir" -ForegroundColor Gray
    }
}

# Тестирование импорта основных модулей
Write-Host "🧪 Тестирование модулей..." -ForegroundColor Yellow
$testScript = @"
try:
    import telegram
    import google.generativeai
    import mem0
    print("✅ Все основные модули доступны")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    exit(1)
"@

$testResult = python -c $testScript
Write-Host $testResult

# Финальная информация
Write-Host ""
Write-Host "🎉 УСТАНОВКА ЗАВЕРШЕНА!" -ForegroundColor Green
Write-Host "=" -repeat 60 -ForegroundColor Green
Write-Host ""
Write-Host "📋 Что дальше:" -ForegroundColor Cyan
Write-Host "1️⃣  Убедитесь, что .env файл содержит все необходимые ключи" -ForegroundColor White
Write-Host "2️⃣  Запустите бота командой: python main.py" -ForegroundColor White
Write-Host "3️⃣  Найдите бота в Telegram и отправьте /start" -ForegroundColor White
Write-Host ""
Write-Host "🔧 Команды управления:" -ForegroundColor Cyan
Write-Host "   Запуск: python main.py" -ForegroundColor Gray
Write-Host "   Остановка: Ctrl+C" -ForegroundColor Gray
Write-Host "   Логи: tail -f firdavs_ai_agent.log" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 Особенности:" -ForegroundColor Cyan
Write-Host "   • mem0 для умной памяти агента" -ForegroundColor Gray
Write-Host "   • Локальная векторная база Chroma" -ForegroundColor Gray
Write-Host "   • Оптимизация токенов Gemini" -ForegroundColor Gray
Write-Host "   • Контекстная память разговоров" -ForegroundColor Gray
Write-Host ""
Write-Host "📞 Поддержка: @FirdavsAIDev" -ForegroundColor Cyan
Write-Host "=" -repeat 60 -ForegroundColor Green