---
name: run-dashboard
description: Запуск, проверка и остановка локального Flask-дашборда аналитики тренеров. Используй, когда нужно поднять веб-отчёт на http://127.0.0.1:5000, убедиться что сервис жив, или корректно его остановить.
---

# run-dashboard

Скил для управления локальным веб-сервисом отчёта (`app/server.py`).

## Когда использовать
- Пользователь просит «открой/запусти отчёт», «подними сайт».
- Нужно проверить, что сервер отвечает.
- Нужно остановить сервер.

## Запуск
```powershell
cd C:\Users\User\Desktop\project\teacher-analytics
pip install -r requirements.txt   # один раз
python app/server.py
```
Адрес: **http://127.0.0.1:5000**

Запускай в фоне (`exec` с background/yieldMs), затем проверяй статус —
не блокируй сессию ожиданием.

## Проверка, что сервис жив
```powershell
try { (Invoke-WebRequest "http://127.0.0.1:5000" -UseBasicParsing).StatusCode }
catch { $_.Exception.Message }
```
Ожидаемый ответ: `200`.

## Быстрая проверка расчётов без браузера
POST реальных файлов на `/analyze`:
```python
import requests, glob
files = [("files", (p.split("\\")[-1], open(p, "rb").read()))
         for p in glob.glob(r"..\data\*.xlsx")]
r = requests.post("http://127.0.0.1:5000/analyze", files=files)
print(r.status_code, r.json()["totals"])
```

## Остановка
- В интерактивном терминале: `Ctrl+C`.
- Фоновый процесс из `exec`: используй `process` (action=kill) с нужным
  sessionId, либо закрой окно терминала.

## Замечания
- Это dev-сервер Flask — только для локального использования, не для
  публичного развёртывания.
- Порт по умолчанию `5000`; если занят — поменяй в `app/server.py`.
- Файлы загружаются в память и не сохраняются на диск; исходные данные
  не изменяются.
