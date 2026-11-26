# QuizForge

[![Build](https://github.com/Mishuig/QuizForge-v0.9.7/actions/workflows/portable-windows.yml/badge.svg)](https://github.com/Mishuig/QuizForge-v0.9.7/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Повністю десктопний застосунок для Windows 10/11 для захищеного тестування з елементами прокторингу.

## Особливості

- Автентифікація через OTP (email)
- Прокторинг: блокування Alt+Tab, скріншоти
- Темна/світла тема з перемикачем
- Адаптивний інтерфейс
- Імпорт тестів з Excel
- Генерація звітів PDF

## Завантаження

[![Download](https://img.shields.io/badge/Download-Portable%20Build-green)](https://github.com/Mishuig/QuizForge-v0.9.7/actions)

1. Перейдіть до [Actions](https://github.com/Mishuig/QuizForge-v0.9.7/actions)
2. Завантажте артефакт `QuizForge-Portable-*.zip`
3. Розпакуйте і запустіть `QuizForge-Admin.exe` або `QuizForge-Client.exe`

## Запуск з коду

```bash
git clone https://github.com/Mishuig/QuizForge-v0.9.7.git
cd QuizForge-v0.9.7
pip install -r requirements.txt
python -m admin.main    # адмін-панель
python -m client.main   # клієнт тестування
```

## Структура

```
QuizForge/
├── admin/           # Адмін-панель
├── client/          # Клієнт тестування
├── core/            # Спільна логіка
├── assets/          # Логотипи, іконки
├── tests/           # Unit тести
├── fonts/           # Шрифти
├── config.json.example
└── requirements.txt
```

## Документація

- [FIRST_RUN.md](FIRST_RUN.md) — перший запуск
- [CONTRIBUTING.md](CONTRIBUTING.md) — розробка

## Ліцензія

MIT — див. [LICENSE](LICENSE)
