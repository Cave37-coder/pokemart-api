"""Staff page: upload the current checklistData.ts, get the regenerated one back.

Runs on the server, so no database URL is needed on a PC.
URL: /admin/checklist-regen/  (staff login required)
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_protect

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
        new_content, stats = regenerate_checklist_content(content)
    except Exception as e:  # format problems / unmapped era, show to staff
        return HttpResponse(_FORM.format(msg=f"<p style='color:#b00'>{e}</p>", token=token), status=400)

    resp = HttpResponse(new_content, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="checklistData.ts"'
    resp["X-Checklist-Stats"] = f"sets={stats['sets']};cards={stats['cards']};index={stats['index']}"
    return resp
