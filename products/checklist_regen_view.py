"""Staff page: upload the current checklistData.ts, get the regenerated one back.

Runs on the server, so no database URL is needed on a PC.
URL: /admin/checklist-regen/  (staff login required)
"""
import hmac
import os

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from products.management.commands.generate_checklist_data import regenerate_checklist_content

_FORM = """<!doctype html><meta charset="utf-8"><title>Regenerate checklistData.ts</title>
<body style="font-family:system-ui;max-width:560px;margin:40px auto">
<h2>Regenerate checklistData.ts</h2>
<p>Choose the current <code>pokemart-frontend/src/lib/checklistData.ts</code>.
You will get the updated file back to save over it, then commit and push.</p>
{msg}
<form method="post" enctype="multipart/form-data">
<input type="hidden" name="csrfmiddlewaretoken" value="{token}">
<input type="file" name="file" accept=".ts" required>
<button type="submit">Regenerate &amp; download</button>
</form></body>"""


@csrf_exempt
def checklist_regen_api(request):
    """Token-authenticated twin of the page below, for the nightly GitHub
    Action in pokemart-frontend (.github/workflows/regen-checklist.yml).
    POST the current checklistData.ts as the raw body with header
    X-Regen-Token; the regenerated file comes back as the response body.
    Token = env CHECKLIST_REGEN_TOKEN (same value as the GitHub secret)."""
    expected = os.environ.get("CHECKLIST_REGEN_TOKEN", "")
    given = request.headers.get("X-Regen-Token", "")
    if request.method != "POST" or not expected or not hmac.compare_digest(expected, given):
        return HttpResponse("Forbidden", status=403)
    try:
        content = request.body.decode("utf-8-sig")
        crlf = "\r\n" in content
        if crlf:
            content = content.replace("\r\n", "\n")
        new_content, stats = regenerate_checklist_content(content)
        if crlf:
            new_content = new_content.replace("\n", "\r\n")
    except Exception as e:
        return HttpResponse(f"Regen failed: {e}", status=400, content_type="text/plain")
    resp = HttpResponse(new_content, content_type="text/plain; charset=utf-8")
    resp["X-Checklist-Stats"] = f"sets={stats['sets']};cards={stats['cards']};index={stats['index']}"
    return resp


@staff_member_required
@csrf_protect
def checklist_regen_view(request):
    from django.middleware.csrf import get_token
    token = get_token(request)
    if request.method != "POST":
        return HttpResponse(_FORM.format(msg="", token=token))

    upload = request.FILES.get("file")
    if not upload:
        return HttpResponse(_FORM.format(msg="<p style='color:#b00'>No file uploaded.</p>", token=token), status=400)
    try:
        content = upload.read().decode("utf-8-sig")
        crlf = "\r\n" in content
        if crlf:
            content = content.replace("\r\n", "\n")
        new_content, stats = regenerate_checklist_content(content)
        if crlf:  # keep the file's Windows line endings so the git diff stays small
            new_content = new_content.replace("\n", "\r\n")
    except Exception as e:  # format problems / unmapped era, show to staff
        from django.utils.html import escape
        return HttpResponse(_FORM.format(msg=f"<p style='color:#b00'>{escape(str(e))}</p>", token=token), status=400)

    resp = HttpResponse(new_content, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="checklistData.ts"'
    resp["X-Checklist-Stats"] = f"sets={stats['sets']};cards={stats['cards']};index={stats['index']}"
    return resp
