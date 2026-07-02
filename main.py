"""
main.py — StashFin Review Bot entry point.
Run directly: python main.py
Automated via GitHub Actions every Monday 9am IST.
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('ReviewBot')


def main():
    log.info('=== StashFin Review Bot starting ===')

    # Step 1 — Fetch 1-2-3★ reviews from Play Store
    log.info('Step 1/5: Fetching reviews...')
    from bot.fetcher import fetch_reviews
    reviews = fetch_reviews()
    if not reviews:
        log.warning('No reviews fetched — nothing to process. Exiting.')
        return

    # Step 2 — Load previous buckets for consistency hint
    log.info('Step 2/5: Loading previous run data...')
    from bot.digest import load_last_run
    last_run     = load_last_run()
    prev_buckets = last_run.get('buckets', [])
    log.info(f'Previous buckets: {[b["name"] for b in prev_buckets] or "none (first run)"}')

    # Step 3 — Discover this week's issue buckets (Pass 1)
    log.info('Step 3/5: Discovering issue buckets with Gemini (Pass 1)...')
    from bot.classifier import discover_buckets, classify_reviews
    buckets = discover_buckets(reviews, prev_buckets)

    # Step 4 — Classify each review into discovered buckets (Pass 2)
    log.info('Step 4/5: Classifying reviews (Pass 2)...')
    classified = classify_reviews(reviews, buckets)

    # Step 5 — Build digest and send
    log.info('Step 5/5: Building digest and sending email...')
    from bot.digest import build_digest, save_last_run
    digest = build_digest(classified, buckets)

    log.info(
    f'Digest: {digest["total"]} reviews | '
    f'Negative: {digest["by_sentiment"].get("Negative", 0)} | '
    f'Signal rate: {digest.get("negative_signal_rate", 0)}% | '
    f'Buckets: {[b["name"] for b in buckets]}'
    )

    from bot.email_publisher import publish_via_email
    publish_via_email(digest)

    # Save for next week's trend comparison
    save_last_run(digest)
    log.info('=== Bot run complete ===')


if __name__ == '__main__':
    main()
