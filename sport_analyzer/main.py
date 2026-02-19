#!/usr/bin/env python3
import sys
import argparse
import logging
from colorama import Fore, Style, init

from config.settings import Config
from collectors.sports_collector import SportsCollector
from collectors.weather_collector import WeatherCollector
from collectors.news_collector import NewsCollector
from collectors.xg_collector import XGCollector
from analyzers.match_analyzer import MatchAnalyzer
from database.migrations import run_migrations
from utils.team_normalizer import normalize_team_name

init(autoreset=True)
logging.basicConfig(level=logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="🏆 Sport Analyzer")
    parser.add_argument("--home",      help="Домашняя команда")
    parser.add_argument("--away",      help="Гостевая команда")
    parser.add_argument("--home-id",   type=int)
    parser.add_argument("--away-id",   type=int)
    parser.add_argument("--city",      help="Город матча")
    parser.add_argument("--date",      help="Дата ISO: 2025-04-20T20:00:00")
    parser.add_argument("--neutral",   action="store_true")
    parser.add_argument("--matches",   action="store_true", help="Список матчей")
    args = parser.parse_args()

    cfg = Config()
    run_migrations(cfg.DB_PATH)

    sports   = SportsCollector(cfg)
    weather  = WeatherCollector()
    news     = NewsCollector(cfg)
    xg       = XGCollector(db_path=cfg.DB_PATH)
    analyzer = MatchAnalyzer(cfg, sports, weather, news, xg_collector=xg)

    print(f"\n{Fore.CYAN}{'═'*55}")
    print(f"  🏆 SPORT ANALYZER")
    print(f"{'═'*55}{Style.RESET_ALL}\n")

    if args.matches:
        matches = sports.get_matches(days_ahead=7)
        if not matches:
            print("  Матчи не найдены (проверьте FOOTBALL_DATA_KEY)")
        for m in matches[:20]:
            date = (m.get("date") or "")[:10]
            print(f"  {date}  {m['home_team']:25} vs {m['away_team']:25}  "
                  f"[{m['home_team_id']} / {m['away_team_id']}]")
        return

    home_raw = args.home
    away_raw = args.away

    if not home_raw or not away_raw:
        print(f"{Fore.YELLOW}Интерактивный режим{Style.RESET_ALL}")
        home_raw = input("  🏠 Домашняя команда: ").strip()
        away_raw = input("  ✈️  Гостевая команда: ").strip()
        if not args.city:
            args.city = input("  📍 Город (Enter — пропуск): ").strip() or None
        if not args.date:
            args.date = input("  📅 Дата (Enter — пропуск): ").strip() or None

    home = normalize_team_name(home_raw)
    away = normalize_team_name(away_raw)

    result = analyzer.analyze_match(
        home_team      = home,
        away_team      = away,
        match_datetime = args.date,
        city           = args.city,
        home_team_id   = args.home_id,
        away_team_id   = args.away_id,
        neutral_field  = args.neutral,
    )

    _print_result(result)


def _print_result(r: dict):
    home    = r["home_team"]
    away    = r["away_team"]
    p       = r["poisson"]
    probs   = r.get("final_probs", p)
    conf    = r["confidence"]
    weather = r["weather"]
    h2h     = r["h2h"]

    print(f"{Fore.WHITE}  {home} vs {away}{Style.RESET_ALL}")
    print()

    # Вероятности
    print(f"{Fore.YELLOW}  Вероятности:{Style.RESET_ALL}")
    _bar(f"🏠 {home[:20]}", probs["home_win"], Fore.GREEN)
    _bar("🤝 Ничья",        probs["draw"],     Fore.YELLOW)
    _bar(f"✈️  {away[:20]}", probs["away_win"], Fore.RED)

    # Голы и тоталы
    print(f"\n{Fore.YELLOW}  Голы / Тоталы:{Style.RESET_ALL}")
    print(f"  Ожид. голы:  🏠 {p['lambda_h']}  ✈️  {p['lambda_a']}  "
          f"(итого {p['total_exp']})")
    print(f"  Тотал Б 1.5: {p['over_1_5']*100:.1f}%  "
          f"Б 2.5: {p['over_2_5']*100:.1f}%  "
          f"Б 3.5: {p['over_3_5']*100:.1f}%")
    print(f"  Обе забьют:  {p['both_score']*100:.1f}%")

    # Погода
    if weather.get("temperature") is not None:
        print(f"\n{Fore.YELLOW}  Погода:{Style.RESET_ALL}")
        print(f"  {weather.get('condition')} | "
              f"{weather.get('temperature')}°C | "
              f"💨 {weather.get('wind_speed')} км/ч | "
              f"🌧️ {weather.get('precipitation')} мм")

    # H2H
    if h2h.get("matches", 0) > 0:
        print(f"\n{Fore.YELLOW}  H2H ({h2h['matches']} матчей):{Style.RESET_ALL}")
        print(f"  {home}: {h2h['home_win_pct']}%  |  "
              f"Ничья: {h2h['draw_pct']}%  |  "
              f"{away}: {h2h['away_win_pct']}%")

    # Уверенность
    color = Fore.GREEN if conf >= 60 else Fore.YELLOW if conf >= 48 else Fore.RED
    print(f"\n  Уверенность: {color}{conf}% {r['confidence_label']}{Style.RESET_ALL}")

    # Рекомендации
    print(f"\n{Fore.YELLOW}  Рекомендации:{Style.RESET_ALL}")
    for rec in r["recommendations"]:
        print(f"  {rec}")
    print()


def _bar(label: str, prob: float, color):
    filled = int(prob * 30)
    bar    = color + "█" * filled + Style.RESET_ALL + "░" * (30 - filled)
    print(f"  {label:<26} |{bar}| {color}{prob*100:5.1f}%{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
