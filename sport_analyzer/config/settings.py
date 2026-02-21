import os

# dotenv — опционально (на хостингах может не быть установлен)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class Config:
    # API Keys
    FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")
    API_FOOTBALL_KEY  = os.getenv("API_FOOTBALL_KEY",  "")
    NEWS_API_KEY      = os.getenv("NEWS_API_KEY",      "")
    GNEWS_KEY         = os.getenv("GNEWS_KEY",         "")

    # Database
    DB_PATH = os.getenv("DB_PATH", "sport_analyzer.db")

    # Analysis weights
    WEIGHTS = {
        "team_form":      0.25,
        "head_to_head":   0.20,
        "home_advantage": 0.15,
        "player_stats":   0.15,
        "injuries":       0.10,
        "weather":        0.05,
        "news_sentiment": 0.05,
        "odds_movement":  0.05,
    }

    MIN_CONFIDENCE = 48
    FORM_MATCHES   = 5
