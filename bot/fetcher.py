"""
fetcher.py — Entry point for data collection.
Calls scraper, calculates average rating from per-star counts,
attaches all weekly stats to each review for digest to read.

Fix: cutoff is rounded to start of day (midnight UTC) so early-morning
reviews are not silently dropped due to the bot run time.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from bot.config import DAYS_TO_FETCH
from bot.scraper import scrape

log = logging.getLogger(__name__)


def fetch_reviews() -> list[dict]:
    now    = datetime.now(timezone.utc)

    # Round cutoff to start of day — prevents losing reviews posted
    # before the bot run time on the first day of the window
    cutoff = (now - timedelta(days=DAYS_TO_FETCH)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    log.info(f'Fetching reviews from {cutoff.date()} to {now.date()} '
             f'(last {DAYS_TO_FETCH} days, cutoff at midnight UTC)')

    reviews, star_counts = scrape(cutoff)

    # Weekly totals
    neg_count    = len(reviews)
    count_4      = star_counts.get(4, 0)
    count_5      = star_counts.get(5, 0)
    weekly_total = neg_count + count_4 + count_5
    signal_rate  = round(neg_count / weekly_total * 100, 1) if weekly_total else 0

    # Weighted average rating — accurate from exact per-star counts
    c1 = star_counts.get(1, 0)
    c2 = star_counts.get(2, 0)
    c3 = star_counts.get(3, 0)
    if weekly_total:
        avg_rating = round(
            (1*c1 + 2*c2 + 3*c3 + 4*count_4 + 5*count_5) / weekly_total, 1
        )
    else:
        avg_rating = 0.0

    log.info(
        f'Fetch done — 1★:{c1} 2★:{c2} 3★:{c3} '
        f'4★:{count_4} 5★:{count_5} | '
        f'Total: {weekly_total} | Avg: {avg_rating}★ | Signal: {signal_rate}%'
    )

    for r in reviews:
        r['weekly_total']  = weekly_total
        r['star_counts']   = star_counts
        r['avg_rating']    = avg_rating
        r['signal_rate']   = signal_rate

    return reviews
