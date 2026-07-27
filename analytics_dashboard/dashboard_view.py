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
    except Exception as e:
        daily_visits, conversion, funnel = [], {}, []
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
        pct = step.get("pct_of_previous", 100)
        bar_color = "#ff6b35" if pct >= 50 else ("#f59e0b" if pct >= 25 else "#dc2626")
        funnel_rows += f'''<div style="margin-bottom:14px">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:13px">
                <span style="color:#fff;font-weight:600">{step.get('step')}</span>
                <span style="color:#888">{step.get('users', 0):,} users {"(" + str(pct) + "% of previous)" if step != funnel[0] else ""}</span>
            </div>
            <div style="background:#12121a;border-radius:6px;height:10px;overflow:hidden">
                <div style="background:{bar_color};height:100%;width:{pct}%;border-radius:6px"></div>
            </div>
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

  {error_block}
  {conversion_cards}

  <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:20px;margin-bottom:24px">
    <h2 style="font-size:15px;margin:0 0 16px;color:#a0a0b0">Daily Visitors</h2>
    <canvas id="visitsChart" height="80"></canvas>
  </div>

  <div style="background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:20px;margin-bottom:24px">
    <h2 style="font-size:15px;margin:0 0 16px;color:#a0a0b0">Funnel: Where People Drop Off</h2>
    {funnel_rows if funnel else '<div style="color:#666;font-size:13px">No funnel data available for this period.</div>'}
  </div>

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
