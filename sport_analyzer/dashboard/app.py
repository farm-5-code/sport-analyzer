"""Streamlit dashboard.

Локальный запуск:
  streamlit run sport_analyzer/dashboard/app.py

Для деплоя (Streamlit Community Cloud / similar):
  - этот файл должен быть выбран как entrypoint
  - requirements.txt должен лежать в корне репозитория
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict

import pandas as pd
import streamlit as st

# Добавляем пакет sport_analyzer в sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.settings import Config
from collectors.sports_collector import SportsCollector
from collectors.weather_collector import WeatherCollector
from collectors.news_collector import NewsCollector
from collectors.xg_collector import XGCollector
from analyzers.match_analyzer import MatchAnalyzer
from database.migrations import run_migrations
from utils.team_normalizer import normalize_team_name


st.set_page_config(
    page_title="Sport Analyzer",
    page_icon="🏆",
    layout="wide",
)

# ── Стили ─────────────────────────────────────────────────────────────

st.markdown(
    """
<style>
.main-header { font-size: 28px; font-weight: 800; margin: 0 0 8px 0; }
.sub-header  { font-size: 18px; font-weight: 700; margin: 12px 0 6px 0; }
.card { border:1px solid #e8e8e8; border-radius: 14px; padding: 14px; margin-bottom: 10px; }
.rec-item { padding: 10px 12px; border-radius: 12px; border: 1px solid #efefef; margin: 8px 0; }
.kpi { font-size: 22px; font-weight: 800; }
.small { color: #777; font-size: 12px; }
.conf-high   { color:#2f9e44; font-weight:700; }
.conf-medium { color:#e67700; font-weight:700; }
.conf-low    { color:#c92a2a; font-weight:700; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Вспомогательные функции ───────────────────────────────────────────

def _save_to_db(result: dict):
    """
    Сохраняет результат анализа в SQLite.
    Исправлено: правильные отступы + всё внутри `with`.
    """
    cfg = Config()
    poisson = result.get("poisson", {})
    p = result.get("final_probs") or {
        "home_win": poisson.get("home_win", 0),
        "draw": poisson.get("draw", 0),
        "away_win": poisson.get("away_win", 0),
    }

    best = max(
        [
            ("home_win", p.get("home_win", 0)),
            ("draw", p.get("draw", 0)),
            ("away_win", p.get("away_win", 0)),
        ],
        key=lambda x: x[1],
    )

    try:
        with sqlite3.connect(cfg.DB_PATH, timeout=10) as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match TEXT,
                    datetime TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    prediction TEXT,
                    confidence REAL,
                    analysis_json TEXT
                )
                """
            )

            c.execute(
                """
                INSERT INTO analyses (match, datetime, prediction, confidence, analysis_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    result.get("match", ""),
                    result.get("datetime", ""),
                    best[0],
                    float(result.get("confidence", 0.0)),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            c.commit()
    except Exception:
        # чтобы приложение не падало из-за БД
        return


def _load_history() -> pd.DataFrame:
    try:
        with sqlite3.connect(Config().DB_PATH, timeout=10) as c:
            return pd.read_sql(
                """
                SELECT created_at, match, prediction, confidence
                FROM analyses
                ORDER BY id DESC
                LIMIT 500
                """,
                c,
            )
    except Exception:
        return pd.DataFrame()


def _load_elo() -> pd.DataFrame:
    try:
        with sqlite3.connect(Config().DB_PATH, timeout=10) as c:
            return pd.read_sql(
                "SELECT name, league, elo FROM team_elo ORDER BY elo DESC",
                c,
            )
    except Exception:
        return pd.DataFrame()


def _prob_bar(label: str, prob: float, color: str):
    width = int(prob * 280)
    st.markdown(
        f'<div style="margin:4px 0">'
        f'<span style="font-weight:600;width:170px;display:inline-block">{label}</span>'
        f'<span style="background:{color};display:inline-block;'
        f'height:20px;border-radius:4px;vertical-align:middle;'
        f'width:{width}px"></span>'
        f'&nbsp;<b>{prob*100:.1f}%</b></div>',
        unsafe_allow_html=True,
    )


# ── Рендер результата ─────────────────────────────────────────────────

def render_result(result: dict):
    home = result.get("home_team", "Home")
    away = result.get("away_team", "Away")

    probs = result.get("final_probs", {})
    poisson = result.get("poisson", {})
    weather = result.get("weather", {})
    h2h = result.get("h2h", {})
    news = result.get("news", {})
    conf = float(result.get("confidence", 0))
    conf_l = result.get("confidence_label", "")

    st.markdown("### Вероятности исходов")
    _prob_bar(f"🏠 {home}", probs.get("home_win", 0), "#51cf66")
    _prob_bar("🤝 Ничья", probs.get("draw", 0), "#ffd43b")
    _prob_bar(f"✈️ {away}", probs.get("away_win", 0), "#ff6b6b")

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⚽ Голы (хоз.)", poisson.get("lambda_h", 0))
    c2.metric("⚽ Голы (гост.)", poisson.get("lambda_a", 0))
    c3.metric("📊 Тотал Б 2.5", f"{poisson.get('over_2_5', 0) * 100:.1f}%")
    c4.metric("✅ Обе забьют", f"{poisson.get('both_score', 0) * 100:.1f}%")

    st.markdown("---")
    t1, t2, t3 = st.columns(3)
    t1.metric("Тотал Б 1.5", f"{poisson.get('over_1_5', 0) * 100:.1f}%")
    t2.metric("Тотал Б 2.5", f"{poisson.get('over_2_5', 0) * 100:.1f}%")
    t3.metric("Тотал Б 3.5", f"{poisson.get('over_3_5', 0) * 100:.1f}%")

    st.markdown("---")
    css = "conf-high" if conf >= 60 else ("conf-medium" if conf >= 48 else "conf-low")
    st.markdown(
        f'<span class="{css}">Уверенность: {conf:.1f}% — {conf_l}</span>',
        unsafe_allow_html=True,
    )

    if weather.get("temperature") is not None:
        with st.expander("🌤️ Погода на матч"):
            w1, w2, w3 = st.columns(3)
            w1.metric("🌡️ Температура", f"{weather.get('temperature')}°C")
            w2.metric("🌧️ Осадки", f"{weather.get('precipitation', 0)} мм")
            w3.metric("💨 Ветер", f"{weather.get('wind_speed', 0)} км/ч")
            st.info(
                f"{weather.get('condition', '')} | "
                f"Влияние: {weather.get('impact_score', 0)}/100"
            )
            for note in weather.get("analysis", []):
                st.caption(note)

    if h2h.get("matches", 0) > 0:
        with st.expander(f"📋 Личные встречи ({h2h['matches']} матчей)"):
            h1, h2c, h3 = st.columns(3)
            h1.metric(f"🏠 {home}", f"{h2h.get('home_win_pct', 0)}%")
            h2c.metric("🤝 Ничья", f"{h2h.get('draw_pct', 0)}%")
            h3.metric(f"✈️ {away}", f"{h2h.get('away_win_pct', 0)}%")

    hn = news.get("home", {})
    an = news.get("away", {})
    if hn or an:
        with st.expander("📰 Новостной фон"):
            n1, n2 = st.columns(2)
            with n1:
                st.markdown(f"**🏠 {home}**")
                st.write(hn.get("sentiment_label", "N/A"))
                for t in hn.get("key_topics", []):
                    st.caption(t)
            with n2:
                st.markdown(f"**✈️ {away}**")
                st.write(an.get("sentiment_label", "N/A"))
                for t in an.get("key_topics", []):
                    st.caption(t)

    with st.expander("💡 Рекомендации", expanded=True):
        for rec in result.get("recommendations", []):
            st.markdown(f'<div class="rec-item">{rec}</div>', unsafe_allow_html=True)

    with st.expander("🔧 Raw JSON"):
        st.json(result)


# ── Страницы ──────────────────────────────────────────────────────────

def render_page_analyze(analyzer: MatchAnalyzer):
    st.markdown('<div class="main-header">🔍 Анализ матча</div>', unsafe_allow_html=True)

    col_f, col_r = st.columns([1, 1.6], gap="large")

    with col_f:
        st.markdown("### Параметры")
        home_raw = st.text_input("🏠 Домашняя команда", placeholder="Arsenal")
        away_raw = st.text_input("✈️ Гостевая команда", placeholder="Chelsea")
        city = st.text_input("📍 Город (необязательно)", placeholder="London")
        d_col, t_col = st.columns(2)
        with d_col:
            match_date = st.date_input("📅 Дата", value=datetime.today())
        with t_col:
            match_time = st.time_input("🕐 Время UTC")
        h_id = st.number_input("ID хозяев (football-data)", value=0, step=1)
        a_id = st.number_input("ID гостей (football-data)", value=0, step=1)
        neutral = st.checkbox("Нейтральное поле")
        run_btn = st.button("🚀 Анализировать", use_container_width=True, type="primary")

    with col_r:
        if run_btn:
            if not home_raw or not away_raw:
                st.error("Введите обе команды")
                return

            home = normalize_team_name(home_raw)
            away = normalize_team_name(away_raw)

            if home != home_raw:
                st.info(f"✏️ {home_raw} → {home}")
            if away != away_raw:
                st.info(f"✏️ {away_raw} → {away}")

            with st.spinner("Анализируем…"):
                result = analyzer.analyze_match(
                    home_team=home,
                    away_team=away,
                    match_datetime=f"{match_date}T{match_time}:00",
                    city=city or None,
                    home_team_id=int(h_id) if h_id else None,
                    away_team_id=int(a_id) if a_id else None,
                    neutral_field=neutral,
                )

            st.session_state["last_result"] = result
            _save_to_db(result)
            render_result(result)

        elif "last_result" in st.session_state:
            render_result(st.session_state["last_result"])


def render_page_schedule(sports: SportsCollector, analyzer: MatchAnalyzer):
    st.markdown('<div class="main-header">📅 Расписание</div>', unsafe_allow_html=True)

    days = st.slider("Дней вперёд", 1, 14, 7)

    with st.spinner("Загружаем…"):
        matches = sports.get_matches(days_ahead=days)

    if not matches:
        st.warning("Матчи не найдены. Проверьте FOOTBALL_DATA_KEY.")
        return

    df = pd.DataFrame(matches)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%d.%m %H:%M")

    disp = df[["date", "competition", "home_team", "away_team"]].rename(
        columns={
            "date": "Дата",
            "competition": "Лига",
            "home_team": "Хозяева",
            "away_team": "Гости",
        }
    )

    leagues = ["Все"] + sorted(disp["Лига"].dropna().unique().tolist())
    sel_l = st.selectbox("Фильтр по лиге", leagues)
    if sel_l != "Все":
        disp = disp[disp["Лига"] == sel_l]

    st.dataframe(disp, use_container_width=True, hide_index=True)

    st.markdown("---")
    filtered_idx = disp.index.tolist()
    if not filtered_idx:
        return

    sel = st.selectbox(
        "Выберите матч для анализа",
        options=filtered_idx,
        format_func=lambda i: (
            f"{disp.loc[i,'Дата']} | {disp.loc[i,'Хозяева']} vs {disp.loc[i,'Гости']}"
        ),
    )

    if st.button("🚀 Анализировать матч"):
        orig = matches[sel]
        with st.spinner("Анализ…"):
            result = analyzer.analyze_match(
                home_team=normalize_team_name(orig["home_team"]),
                away_team=normalize_team_name(orig["away_team"]),
                match_datetime=orig.get("date"),
                home_team_id=orig.get("home_team_id"),
                away_team_id=orig.get("away_team_id"),
            )
        st.session_state["last_result"] = result
        _save_to_db(result)
        render_result(result)


def render_page_history():
    st.markdown('<div class="main-header">📊 История прогнозов</div>', unsafe_allow_html=True)
    df = _load_history()
    if df.empty:
        st.info("История пуста — сделайте первый анализ")
        return

    s1, s2, s3 = st.columns(3)
    s1.metric("Всего", len(df))
    s2.metric("Средняя уверенность", f"{df['confidence'].mean():.1f}%")
    s3.metric(">60% уверенность", int((df["confidence"] > 60).sum()))

    st.dataframe(
        df.rename(
            columns={
                "created_at": "Дата",
                "match": "Матч",
                "prediction": "Прогноз",
                "confidence": "Уверенность %",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    chart = df[["created_at", "confidence"]].copy()
    chart["created_at"] = pd.to_datetime(chart["created_at"])
    st.line_chart(chart.set_index("created_at"))


def render_page_elo():
    st.markdown('<div class="main-header">📈 ELO рейтинги</div>', unsafe_allow_html=True)
    st.info("ELO обновляется через `python scripts/update_elo.py`. Начальный рейтинг: 1500.")

    df = _load_elo()
    if df.empty:
        st.warning("Рейтинги ещё не сформированы")
        return

    df = df.sort_values("elo", ascending=False).reset_index(drop=True)
    df.index += 1

    leagues = ["Все"] + sorted(df["league"].dropna().unique().tolist())
    sel = st.selectbox("Фильтр по лиге", leagues)
    if sel != "Все":
        df = df[df["league"] == sel]

    left, right = st.columns([1, 1.4])
    with left:
        st.dataframe(
            df.rename(columns={"name": "Команда", "league": "Лига", "elo": "ELO"}),
            use_container_width=True,
        )
    with right:
        if not df.empty:
            st.bar_chart(df.head(20).set_index("name")["elo"])


# ════════════════════════════════════════════════════════════════════
# Инициализация
# ════════════════════════════════════════════════════════════════════

@st.cache_resource
def init_resources():
    cfg = Config()
    run_migrations(cfg.DB_PATH)
    sports = SportsCollector(cfg, db_path=cfg.DB_PATH)
    weather = WeatherCollector(db_path=cfg.DB_PATH)
    news = NewsCollector(cfg)
    xg = XGCollector(db_path=cfg.DB_PATH)
    analyzer = MatchAnalyzer(cfg, sports, weather, news, xg_collector=xg)
    return analyzer, sports


analyzer, sports = init_resources()

with st.sidebar:
    st.markdown("## 🏆 Sport Analyzer")
    st.markdown("---")
    page = st.radio(
        "Навигация",
        ["🔍 Анализ матча", "📅 Расписание", "📊 История", "📈 ELO рейтинги"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("football-data.org · open-meteo · thesportsdb")

if page == "🔍 Анализ матча":
    render_page_analyze(analyzer)
elif page == "📅 Расписание":
    render_page_schedule(sports, analyzer)
elif page == "📊 История":
    render_page_history()
elif page == "📈 ELO рейтинги":
    render_page_elo()
