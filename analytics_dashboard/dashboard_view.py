# analytics_dashboard/dashboard_view.py
#
# Server-rendered analytics dashboard for staff, matching the existing
# admin tool pattern used by manage_set_view.py and the manual invoice POS
# screens (staff_member_required, plain HTML + embedded JS, dark theme
# consistent with the rest of the site).
#
# Deliberately calls the services.* functions directly rather than hitting
# the DRF /api/analytics/summary/ JSON endpoint via fetch() -- that
# endpoint uses IsAdminUser (JWT auth), while this page uses Django's
# session auth (staff_member_required), so a client-side fetch would need
# a JWT this page's users don't have. Calling services directly server-side
# sidesteps that mismatch entirely and is simpler.

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse

from . import services


@staff_member_required
def dashboard_page(request):
    days = int(request.GET.get("days", 30))
    error = None

    try:
        daily_visits = services.get_daily_visits(days=days)
        conversion = services.get_conversion_summary(days=days)
        funnel = services.get_funnel(days=days)
        top_pages = services.get_top_pages(days=days)
        section_engagement = services.get_section_engagement(days=days)
    except Exception as e:
        daily_visits, conversion, funnel, top_pages, section_engagement = [], {}, [], [], []
        error = str(e)

    daily_visits_json = json.dumps(daily_visits)
    funnel_json = json.dumps(funnel)

    error_block = ""
    if error:
        error_block = f'''<div style="background:#3a1a1a;border:1px solid #dc2626;border-radius:8px;padding:16px;margin-bottom:20px;color:#f87171;font-size:13px">
            Could not load GA4 data: {error}<br>
            <span style="color:#888;font-size:11px">Check that GA4_PROPERTY_ID and GOOGLE_APPLICATION_CREDENTIALS_JSON are set correctly in Railway, and that the service account has Viewer access on the GA4 property.</span>
        </div>'''

    conversion_cards = ""
    if conversion:
        conversion_cards = f'''
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(160px, 1fr));gap:14px;margin-bottom:28px">
            <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:10px;padding:16px">
                <div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Sessions</div>
                <div style="font-size:26px;font-weight:800;color:#fff">{conversion.get('sessions', 0):,}</div>
            </div>
            <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:10px;padding:16px">
                <div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Purchases</div>
                <div style="font-size:26px;font-weight:800;color:#fff">{conversion.get('purchases', 0):,}</div>
            </div>
            <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:10px;padding:16px">
                <div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Conversion Rate</div>
                <div style="font-size:26px;font-weight:800;color:#ff6b35">{conversion.get('conversion_rate', 0)}%</div>
            </div>
            <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:10px;padding:16px">
                <div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Revenue</div>
                <div style="font-size:26px;font-weight:800;color:#4ade80">R {conversion.get('revenue', 0):,.2f}</div>
            </div>
        </div>'''

    funnel_rows = ""
    for step in funnel:
        pct = step.get("pct_of_top", 100)
        bar_width = min(pct, 100)
        bar_color = "#ff6b35" if pct >= 50 else ("#f59e0b" if pct >= 25 else "#dc2626")
        pct_label = "" if step == funnel[0] else f"({pct}% of View Card)"
        funnel_rows += f'''<div style="margin-bottom:14px">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:13px">
                <span style="color:#fff;font-weight:600">{step.get('step')}</span>
                <span style="color:#888">{step.get('users', 0):,} users {pct_label}</span>
            </div>
            <div style="background:#12121a;border-radius:6px;height:10px;overflow:hidden">
                <div style="background:{bar_color};height:100%;width:{bar_width}%;border-radius:6px"></div>
            </div>
        </div>'''

    # Michael, 2026-09-03: "the site analytics don't add up" -- explains why
    # a step can show more than 100% of View Card, rather than hiding it.
    funnel_note = ""
    if funnel:
        funnel_note = '''<div style="color:#666;font-size:11px;margin-top:6px">
            Each step counts everyone who did that action anywhere in the period, not one strict path through the site --
            a step can occasionally sit close to (or, rarely, above) 100% if returning visitors reach checkout with items
            already in their cart from an earlier visit, without viewing a card again in this window.
        </div>'''

    top_pages_rows = ""
    for p in top_pages:
        top_pages_rows += f'''<tr style="border-bottom:1px solid #22222e">
            <td style="padding:8px;color:#ccc;font-family:monospace;font-size:12px">{p.get('path')}</td>
            <td style="padding:8px;color:#fff;text-align:right">{p.get('views', 0):,}</td>
            <td style="padding:8px;color:#888;text-align:right">{p.get('users', 0):,}</td>
        </tr>'''

    top_pages_table = f'''<div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:20px;margin-bottom:24px">
        <h2 style="font-size:15px;margin:0 0 4px;color:#a0a0b0">Top Pages</h2>
        <div style="color:#555;font-size:11px;margin-bottom:14px">Which pages people actually reach, ranked by views -- the closest stable-API equivalent to "page entrances".</div>
        <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead><tr style="text-align:left;color:#888;border-bottom:1px solid #2a2a3a">
                <th style="padding:6px 8px">Page</th>
                <th style="padding:6px 8px;text-align:right">Views</th>
                <th style="padding:6px 8px;text-align:right">Visitors</th>
            </tr></thead>
            <tbody>{top_pages_rows if top_pages_rows else '<tr><td colspan="3" style="padding:12px;color:#666">No page data for this period.</td></tr>'}</tbody>
        </table>
        </div>
    </div>'''

    section_cards = ""
    for s in section_engagement:
        section_cards += f'''<div style="background:#12121a;border:1px solid #2a2a3a;border-radius:10px;padding:16px;flex:1;min-width:200px">
            <div style="color:#fff;font-weight:700;font-size:14px;margin-bottom:10px">{s.get('section')}</div>
            <div style="display:flex;gap:18px">
                <div><div style="color:#888;font-size:10px;text-transform:uppercase">Views</div><div style="color:#fff;font-size:18px;font-weight:700">{s.get('views', 0):,}</div></div>
                <div><div style="color:#888;font-size:10px;text-transform:uppercase">Sessions</div><div style="color:#fff;font-size:18px;font-weight:700">{s.get('sessions', 0):,}</div></div>
                <div><div style="color:#888;font-size:10px;text-transform:uppercase">Visitors</div><div style="color:#fff;font-size:18px;font-weight:700">{s.get('users', 0):,}</div></div>
            </div>
        </div>'''

    section_engagement_block = f'''<div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:20px;margin-bottom:24px">
        <h2 style="font-size:15px;margin:0 0 14px;color:#a0a0b0">Community &amp; Checklists Engagement</h2>
        <div style="display:flex;gap:14px;flex-wrap:wrap">{section_cards if section_cards else '<div style="color:#666;font-size:13px">No data for this period.</div>'}</div>
    </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Site Analytics - PokeBulk SA</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
* {{ box-sizing:border-box }}
body {{ font-family:Arial,sans-serif;background:#0d0d12;color:#eee;padding:24px;margin:0 }}
select {{ background:#1a1a24;border:1px solid #2a2a3a;color:#fff;padding:8px 14px;border-radius:6px;font-size:13px }}
a {{ color:#ff6b35 }}
</style>
</head><body>
<div style="max-width:1100px;margin:0 auto">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px">
    <div>
      <h1 style="font-size:22px;margin:0 0 4px">Site Analytics</h1>
      <div style="color:#888;font-size:13px">Live from Google Analytics (GA4)</div>
    </div>
    <form method="get">
      <select name="days" onchange="this.form.submit()">
        <option value="7" {"selected" if days == 7 else ""}>Last 7 days</option>
        <option value="30" {"selected" if days == 30 else ""}>Last 30 days</option>
        <option value="90" {"selected" if days == 90 else ""}>Last 90 days</option>
      </select>
    </form>
  </div>
  <div style="margin-bottom:24px"><a href="/admin/store-overview/" style="font-size:12px">→ Store Overview (real stock &amp; sales data)</a></div>

  {error_block}
  {conversion_cards}

  <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:20px;margin-bottom:24px">
    <h2 style="font-size:15px;margin:0 0 16px;color:#a0a0b0">Daily Visitors</h2>
    <canvas id="visitsChart" height="80"></canvas>
  </div>

  <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:20px;margin-bottom:24px">
    <h2 style="font-size:15px;margin:0 0 16px;color:#a0a0b0">Funnel: Where People Drop Off</h2>
    {funnel_rows if funnel else '<div style="color:#666;font-size:13px">No funnel data available for this period.</div>'}
    {funnel_note}
  </div>

  {top_pages_table}
  {section_engagement_block}

  <div style="color:#555;font-size:11px;text-align:center;margin-top:20px">
    Data reflects ad-blocker-affected client-side tracking -- treat as directional, not exact. Compare conversion rate against a rough e-commerce benchmark of ~2.5-3%.
  </div>
</div>

<script>
const dailyVisits = {daily_visits_json};
const ctx = document.getElementById('visitsChart');
if (dailyVisits.length > 0) {{
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: dailyVisits.map(d => d.date),
      datasets: [{{
        label: 'Visitors',
        data: dailyVisits.map(d => d.visitors),
        borderColor: '#ff6b35',
        backgroundColor: 'rgba(255,107,53,0.1)',
        fill: true,
        tension: 0.3,
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#888' }}, grid: {{ color: '#2a2a3a' }} }},
        y: {{ ticks: {{ color: '#888' }}, grid: {{ color: '#2a2a3a' }}, beginAtZero: true }}
      }}
    }}
  }});
}} else {{
  ctx.parentElement.innerHTML += '<div style="color:#666;font-size:13px;margin-top:10px">No visitor data available for this period.</div>';
}}
</script>
</body></html>'''

    return HttpResponse(html, content_type="text/html; charset=utf-8")
