# 🚀 Быстрый бесплатный деплой (самый простой — Streamlit Community Cloud)

## Вариант A: Streamlit Community Cloud (бесплатно, проще всего)
1) Создай репозиторий на GitHub (можно с телефона).
2) Загрузи туда содержимое папки `sport_analyzer/` (или просто залей zip и распакуй в репозитории).
3) На сайте Streamlit Community Cloud выбери **New app** → репозиторий → файл `dashboard/app.py`.
4) В настройках **Secrets** добавь ключи (как в `.env.example`):
   - `FOOTBALL_DATA_KEY`
   - `NEWS_API_KEY` (опционально)
   - `GNEWS_KEY` (опционально)

## Вариант B: Render (есть бесплатный тариф, но может засыпать)
- Web Service → Python → старт-команда:
  `streamlit run dashboard/app.py --server.port $PORT --server.address 0.0.0.0`

## Важно
- Реальный секретный `.env` **не коммить**. На деплое ключи задаются в Secrets/Environment.
- Локально:
  - `pip install -r requirements.txt`
  - `streamlit run dashboard/app.py`
