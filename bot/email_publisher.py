"""
email_publisher.py
Single email to all recipients.
- Header shows weekly total (all stars) and negative signal rate
- No sentiment score
- No team color coding
- Cards for buckets with 3+ reviews, compact list for lower volume
- Signal-based framing throughout
- Footer disclaimer
"""
from __future__ import annotations
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bot.config import GMAIL_SENDER, GMAIL_APP_PASSWORD, EMAIL_ALL

log = logging.getLogger(__name__)

CARD_COLORS = [
    '#1F4E78', '#C00000', '#7030A0', '#ED7D31',
    '#375623', '#2E75B6', '#8B5A2B', '#4472C4',
]

ALWAYS_COMPACT   = {'General Complaints', 'Uncategorized / No Text',
                    'Irrelevant / Gibberish', 'Positive Feedback'}
FULL_CARD_MIN    = 3


def _delta_html(n: int) -> str:
    if n > 0:
        return f'<span style="color:#C00000;font-weight:bold">↑ +{n} vs last week</span>'
    if n < 0:
        return f'<span style="color:#375623;font-weight:bold">↓ {n} vs last week</span>'
    return '<span style="color:#888">→ same as last week</span>'


def _signal_rate_color(rate: float) -> str:
    if rate <= 5:   return '#375623'
    if rate <= 10:  return '#ED7D31'
    return '#C00000'


def _issue_card(cat: str, count: int, delta: int, data: dict, color: str) -> str:
    subs     = data.get('sub_categories', {})
    examples = data.get('examples', [])

    sub_rows = ''
    for sub, n in sorted(subs.items(), key=lambda x: -x[1])[:3]:
        label    = sub[:90] + ('…' if len(sub) > 90 else '')
        sub_rows += (
            f'<tr><td style="padding:3px 0;font-size:12px;color:#444;line-height:1.4">'
            f'• {label}: <strong>{n}</strong></td></tr>'
        )

    ex_html = ''
    if examples:
        ex_html = (
            f'<tr><td style="padding:8px 0 0 0">'
            f'<div style="background:#F8F8F8;border-left:3px solid {color};'
            f'padding:7px 10px;font-size:11px;color:#555;font-style:italic;'
            f'border-radius:0 4px 4px 0;line-height:1.5">{examples[0]}</div>'
            f'</td></tr>'
        )

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="border-radius:10px;overflow:hidden;border:1px solid #E0E0E0;
                  background:#fff;height:100%">
      <tr>
        <td style="background:{color};padding:10px 14px">
          <span style="color:#fff;font-weight:bold;font-size:13px">{cat}</span>
        </td>
      </tr>
      <tr>
        <td style="padding:12px 14px 4px 14px;background:#FAFBFD">
          <span style="font-size:32px;font-weight:bold;color:{color}">{count}</span>
          <span style="font-size:12px;color:#666;margin-left:6px">user concerns</span><br>
          <span style="font-size:12px">{_delta_html(delta)}</span>
        </td>
      </tr>
      <tr>
        <td style="padding:10px 14px 4px 14px">
          <table width="100%" cellpadding="0" cellspacing="0">{sub_rows}</table>
        </td>
      </tr>
      <tr>
        <td style="padding:0 14px 14px 14px">
          <table width="100%" cellpadding="0" cellspacing="0">{ex_html}</table>
        </td>
      </tr>
    </table>"""


def _build_html(digest: dict) -> str:
    date_range   = digest['date_range']
    prev_range   = digest.get('prev_date_range', 'N/A')
    total        = digest['total']            # 1-2-3★ captured
    total_delta  = digest.get('total_delta', 0)
    weekly_total = digest.get('weekly_total', 0)   # all stars
    prev_weekly  = digest.get('prev_weekly_total', 0)
    weekly_delta = weekly_total - prev_weekly
    sig_rate     = digest.get('negative_signal_rate', 0)
    prev_rate    = digest.get('prev_signal_rate', None)
    neg          = digest['by_sentiment'].get('Negative', 0)
    neu          = digest['by_sentiment'].get('Neutral', 0)
    pos          = digest['by_sentiment'].get('Positive', 0)
    top_issues   = digest['top_issues']
    spikes       = digest.get('spikes', [])
    src          = _signal_rate_color(sig_rate)

    # Signal rate trend
    if prev_rate is not None:
        rate_diff  = round(sig_rate - prev_rate, 1)
        rate_trend = (
            f'↑ +{rate_diff}% vs last week' if rate_diff > 0
            else f'↓ {rate_diff}% vs last week' if rate_diff < 0
            else '→ unchanged'
        )
        rate_color = '#C00000' if rate_diff > 0 else '#375623' if rate_diff < 0 else '#888'
    else:
        rate_trend = 'First run'
        rate_color = '#888'

    # Split full cards vs compact
    display    = [(c, n, d, t) for c, n, d, t in top_issues
                  if c != 'Uncategorized / No Text']
    full_cards = [(c, n, d, t) for c, n, d, t in display
                  if n >= FULL_CARD_MIN and c not in ALWAYS_COMPACT]
    compact    = [(c, n, d, t) for c, n, d, t in display
                  if n < FULL_CARD_MIN or c in ALWAYS_COMPACT]

    # ── Spike banner ──────────────────────────────────────────────
    spike_html = ''
    if spikes:
        rows = ''.join(
            f'<tr>'
            f'<td style="padding:5px 12px;font-weight:bold;color:#7D4E00">{cat}</td>'
            f'<td style="padding:5px 12px;color:#555">{count} concerns</td>'
            f'<td style="padding:5px 12px;font-weight:bold;color:#C00000">{label}</td>'
            f'</tr>'
            for cat, count, label, _ in spikes
        )
        spike_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#FFF3CD;border-left:5px solid #ED7D31;
                      border-radius:0 8px 8px 0;margin-bottom:24px">
          <tr><td style="padding:12px 16px 6px 16px;font-weight:bold;
                         font-size:14px;color:#7D4E00">
            ⚠️ Notable This Week — New Signals or Volume Increases
          </td></tr>
          <tr><td style="padding:0 8px 10px 8px">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr style="background:#FFE8A0">
                <th style="padding:5px 12px;text-align:left;font-size:12px">Concern Area</th>
                <th style="padding:5px 12px;text-align:left;font-size:12px">Volume</th>
                <th style="padding:5px 12px;text-align:left;font-size:12px">Signal</th>
              </tr>
              {rows}
            </table>
          </td></tr>
        </table>"""

    # ── Card grid ─────────────────────────────────────────────────
    cards_html = ''
    for i in range(0, len(full_cards), 2):
        color_l          = CARD_COLORS[i % len(CARD_COLORS)]
        lcat, ln, ld, _  = full_cards[i]
        left_card        = _issue_card(
            lcat, ln, ld,
            digest['by_category'].get(lcat, {}), color_l
        )
        right_card = ''
        if i + 1 < len(full_cards):
            color_r         = CARD_COLORS[(i+1) % len(CARD_COLORS)]
            rcat, rn, rd, _ = full_cards[i+1]
            right_card      = _issue_card(
                rcat, rn, rd,
                digest['by_category'].get(rcat, {}), color_r
            )
        cards_html += f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px">
          <tr>
            <td width="48%" valign="top">{left_card}</td>
            <td width="4%"></td>
            <td width="48%" valign="top">{right_card}</td>
          </tr>
        </table>"""

    # ── Compact list ──────────────────────────────────────────────
    compact_html = ''
    if compact:
        rows = ''.join(
            f'<tr>'
            f'<td style="padding:5px 10px;font-size:12px;color:#444;'
            f'border-bottom:1px solid #EEE">{cat}</td>'
            f'<td style="padding:5px 10px;font-size:12px;font-weight:bold;'
            f'color:#1F4E78;border-bottom:1px solid #EEE">{n}</td>'
            f'<td style="padding:5px 10px;font-size:12px;border-bottom:1px solid #EEE">'
            f'{_delta_html(d)}</td>'
            f'</tr>'
            for cat, n, d, _ in compact
        )
        compact_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px">
          <tr><td colspan="3" style="padding:10px 0 6px 0;font-size:13px;
                                      font-weight:bold;color:#555">
            Also raised this week (lower volume):
          </td></tr>
          <tr style="background:#F5F5F5">
            <th style="padding:5px 10px;text-align:left;font-size:11px;color:#888">
              Concern Area</th>
            <th style="padding:5px 10px;text-align:left;font-size:11px;color:#888">
              Count</th>
            <th style="padding:5px 10px;text-align:left;font-size:11px;color:#888">
              vs Last Week</th>
          </tr>
          {rows}
        </table>"""

    # ── Top 3 actions ─────────────────────────────────────────────
    action_rows = ''
    for rank, (cat, count, delta, _) in enumerate(full_cards[:3], 1):
        color = CARD_COLORS[(rank-1) % len(CARD_COLORS)]
        action_rows += (
            f'<tr><td style="padding:7px 0;font-size:13px;'
            f'border-bottom:1px solid #E8EEF4">'
            f'<span style="background:{color};color:#fff;border-radius:4px;'
            f'padding:2px 8px;font-weight:bold;margin-right:8px">{rank}</span>'
            f'<strong style="color:{color}">{cat}</strong>'
            f' — {count} concerns &nbsp;{_delta_html(delta)}'
            f'</td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:#EEF2F7;
             font-family:Arial,sans-serif;color:#222">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:24px 12px">
<table width="640" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.08)">

  <!-- Header -->
  <tr><td style="background:#1F4E78;padding:22px 28px">
    <div style="font-size:21px;font-weight:bold;color:#fff">
      📊 StashFin Play Store — Weekly Review Signal
    </div>
    <div style="font-size:13px;color:rgba(255,255,255,0.75);margin-top:5px">
      {date_range} &nbsp;|&nbsp; Comparison vs {prev_range}
    </div>
  </td></tr>

  <!-- KPI strip -->
  <tr><td style="background:#F7F9FC;border-bottom:1px solid #E5EAF0">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>

      <!-- Total all stars -->
      <td width="33%" align="center"
          style="padding:18px 10px;border-right:1px solid #DDE5EF">
        <div style="font-size:11px;color:#888;margin-bottom:4px;font-weight:bold;
                    text-transform:uppercase;letter-spacing:0.5px">
          Total Reviews This Week
        </div>
        <div style="font-size:34px;font-weight:bold;color:#1F4E78">
          {weekly_total if weekly_total else '—'}
        </div>
        <div style="font-size:11px;color:#888;margin-top:2px">All star ratings</div>
        <div style="font-size:11px;margin-top:3px">{_delta_html(weekly_delta)}</div>
      </td>

      <!-- 1-2-3 star captured -->
      <td width="33%" align="center"
          style="padding:18px 10px;border-right:1px solid #DDE5EF">
        <div style="font-size:11px;color:#888;margin-bottom:4px;font-weight:bold;
                    text-transform:uppercase;letter-spacing:0.5px">
          1-2-3★ Reviews
        </div>
        <div style="font-size:34px;font-weight:bold;color:#C00000">{total}</div>
        <div style="font-size:11px;margin-top:2px">
          <span style="color:#C00000">● Negative: {neg}</span> &nbsp;
          <span style="color:#888">● Neutral: {neu}</span> &nbsp;
          <span style="color:#375623">● Positive: {pos}</span>
        </div>
        <div style="font-size:11px;margin-top:3px">{_delta_html(total_delta)}</div>
      </td>

      <!-- Negative signal rate -->
      <td width="33%" align="center" style="padding:18px 10px">
        <div style="font-size:11px;color:#888;margin-bottom:4px;font-weight:bold;
                    text-transform:uppercase;letter-spacing:0.5px">
          Negative Signal Rate
        </div>
        <div style="font-size:34px;font-weight:bold;color:{src}">
          {sig_rate}<span style="font-size:16px">%</span>
        </div>
        <div style="font-size:11px;color:#888;margin-top:2px">
          of all reviews this week
        </div>
        <div style="font-size:11px;color:{rate_color};margin-top:3px">
          {rate_trend}
        </div>
      </td>

    </tr></table>
  </td></tr>

  <!-- Body -->
  <tr><td style="padding:24px 28px">

    {spike_html}

    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:18px">
      <tr><td style="border-bottom:2px solid #E5EAF0;padding-bottom:8px">
        <span style="font-size:15px;font-weight:bold;color:#1F4E78">
          What users raised this week — {len(full_cards) + len(compact)} concern areas
        </span>
      </td></tr>
    </table>

    {cards_html}
    {compact_html}

    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#F0F4FA;border-radius:8px;margin-top:8px">
      <tr><td style="padding:16px 20px">
        <div style="font-size:14px;font-weight:bold;color:#1F4E78;margin-bottom:12px">
          🎯 Top concerns by volume this week
        </div>
        <table width="100%" cellpadding="0" cellspacing="0">
          {action_rows}
        </table>
      </td></tr>
    </table>

  </td></tr>

  <!-- Footer -->
  <tr><td style="background:#F5F7FA;padding:16px 28px;
                  border-top:1px solid #E5EAF0">
    <div style="font-size:11px;color:#888;line-height:1.7">
      <strong style="color:#555">Note:</strong>
      These reviews reflect user perception and may include misunderstandings,
      awareness gaps, or one-sided accounts. This report surfaces signals for
      discussion — not confirmed product failures. Each concern area should be
      investigated before conclusions are drawn.<br><br>
      Auto-generated by StashFin Review Bot &nbsp;|&nbsp;
      Covers {date_range} &nbsp;|&nbsp;
      1-2-3★ reviews analysed, 4-5★ counted only &nbsp;|&nbsp;
      Concern areas discovered dynamically each week &nbsp;|&nbsp;
      Contact Vishal (Marketing) for queries
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""
    return html


def publish_via_email(digest: dict) -> None:
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        log.warning('Gmail credentials not set — skipping email')
        return
    if not EMAIL_ALL:
        log.warning('EMAIL_ALL is empty — no recipients configured')
        return

    html       = _build_html(digest)
    top        = digest['top_issues']
    spikes     = digest.get('spikes', [])
    date_range = digest['date_range']
    sig_rate   = digest.get('negative_signal_rate', 0)

    # Short clean subject line
    top_names  = ' · '.join(c for c, _, _, _ in top[:3]) if top else 'No concerns'
    spike_flag = ' ⚠️' if spikes else ''

    subject = (
        f'StashFin Reviews | {date_range} | '
        f'{digest["total"]} negative ({sig_rate}%){spike_flag} | {top_names}'
    )

    msg            = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = GMAIL_SENDER
    msg['To']      = ', '.join(EMAIL_ALL)
    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, EMAIL_ALL, msg.as_string())
        log.info(f'Email sent to {EMAIL_ALL}')
    except Exception as e:
        log.error(f'Email send failed: {e}')
        raise
