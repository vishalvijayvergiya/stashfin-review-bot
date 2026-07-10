"""
fetcher.py — Entry point for data collection.

Date window fix:
  If bot runs on July 6, window is June 29 00:00 UTC → July 5 23:59 UTC.
  Today is EXCLUDED so the window is always a complete 7-day period.
  Reviews posted today (partially complete day) are not included.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from bot.config import DAYS_TO_FETCH
from bot.scraper import scrape

log = logging.getLogger(__name__)


def fetch_reviews() -> list[dict]:
    now = datetime.now(timezone.utc)

    # End of yesterday — exclude today (incomplete day)
    end_of_yesterday = (now - timedelta(days=1)).replace(
        hour=23, minute=59, second=59, microsecond=0
    )

    # Start of window — DAYS_TO_FETCH days before end of yesterday
    start_of_window = (end_of_yesterday - timedelta(days=DAYS_TO_FETCH - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    log.info(
        f'Fetching reviews: {start_of_window.strftime("%d %b %Y")} → '
        f'{end_of_yesterday.strftime("%d %b %Y")} '
        f'(today {now.strftime("%d %b")} excluded)'
    )

    reviews, star_counts = scrape(start_of_window, end_of_yesterday)

    # Totals
    neg_count    = len(reviews)
    count_4      = star_counts.get(4, 0)
    count_5      = star_counts.get(5, 0)
    weekly_total = neg_count + count_4 + count_5
    signal_rate  = round(neg_count / weekly_total * 100, 1) if weekly_total else 0

    # Weighted average rating
    c1 = star_counts.get(1, 0)
    c2 = star_counts.get(2, 0)
    c3 = star_counts.get(3, 0)
    avg_rating = round(
        (1*c1 + 2*c2 + 3*c3 + 4*count_4 + 5*count_5) / weekly_total, 1
    ) if weekly_total else 0.0

    log.info(
        f'1★:{c1} 2★:{c2} 3★:{c3} 4★:{count_4} 5★:{count_5} | '
        f'Total:{weekly_total} | Avg:{avg_rating}★ | Signal:{signal_rate}%'
    )

    # Diagnostic per star
    log.info('=' * 50)
    log.info('SCRAPER DIAGNOSTIC — compare with Play Console')
    log.info(f'1★ : {c1}')
    log.info(f'2★ : {c2}')
    log.info(f'3★ : {c3}')
    log.info(f'4★ : {count_4}')
    log.info(f'5★ : {count_5}')
    log.info(f'TOTAL SCRAPED    : {weekly_total}')
    log.info(f'1-2-3★ with text : {sum(1 for r in reviews if r.get("has_text"))}')
    log.info(f'1-2-3★ no text   : {sum(1 for r in reviews if not r.get("has_text"))}')
    log.info('=' * 50)

    # Attach stats to every review
    for r in reviews:
        r['weekly_total']     = weekly_total
        r['star_counts']      = star_counts
        r['avg_rating']       = avg_rating
        r['signal_rate']      = signal_rate
        r['window_start']     = start_of_window.strftime('%d %b %Y')
        r['window_end']       = end_of_yesterday.strftime('%d %b %Y')

    return reviews
