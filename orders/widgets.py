"""
Custom admin widget for Order.status.

The real <select name="status" id="id_status"> Django needs is still
rendered and still what actually submits on Save -- it's just visually
hidden. On top of it sits a clickable checklist for the 7 statuses that
form a real sequential pipeline (Order Received through Complete):
clicking any step ticks everything before it and unticks everything
after, so jumping from "just received" to "packed and booked" is one
click + one Save instead of three separate dropdown-select-save round
trips. It's still exactly ONE real status value underneath -- this is
a friendlier picker, not independent per-step tracking.

Awaiting Payment / Awaiting EFT Payment / Cancelled aren't part of the
sequential pipeline (a cancelled order isn't "further along" than a
packed one), so they live in a small separate "not in the pipeline yet /
exception" dropdown instead of the checklist.

No model changes, no migration -- formfield_for_dbfield in OrderAdmin
swaps this in for the existing status field only.
"""
import json

from django import forms
from django.utils.safestring import mark_safe


class StatusStepperWidget(forms.Select):

    STEPS = [
        ('pending',   'Order Received'),
        ('printed',   'Order Printed'),
        ('packed',    'Order Packed'),
        ('booked',    'Courier Booking'),
        ('ready',     'Ready for Collection'),
        ('collected', 'Courier Collected'),
        ('invoiced',  'Complete'),
    ]
    OTHER = [
        ('', '— choose —'),
        ('awaiting_payment', 'Awaiting Payment'),
        ('pending_eft', 'Awaiting EFT Payment'),
        ('cancelled', 'Cancelled'),
    ]

    def render(self, name, value, attrs=None, renderer=None):
        select_html = super().render(name, value, attrs, renderer)
        # Keep the real <select> in the DOM (it's what submits) -- just hide it.
        select_html = select_html.replace('<select', '<select style="display:none"', 1)

        widget_id = (attrs or {}).get('id', 'id_%s' % name)
        pipeline_json = json.dumps([code for code, _ in self.STEPS])

        checklist_items = ''.join(
            '''<div class="status-step" data-code="%s" style="display:flex;align-items:center;gap:6px;padding:4px 2px;cursor:pointer;user-select:none">
                <input type="checkbox" class="status-step-box" style="pointer-events:none;margin:0">
                <span>%s</span>
            </div>''' % (code, label)
            for code, label in self.STEPS
        )

        other_options = ''.join(
            '<option value="%s">%s</option>' % (code, label) for code, label in self.OTHER
        )

        html = '''
%s
<div class="status-stepper" style="max-width:260px;margin-top:4px">
    <div class="status-checklist">%s</div>
    <div style="margin-top:6px;font-size:11px;opacity:0.65">Not in the pipeline yet / exception:</div>
    <select class="status-other" style="margin-top:3px">%s</select>
</div>
<script>
(function() {
    var sel = document.getElementById(%s);
    if (!sel) return;
    var wrap = sel.nextElementSibling;
    var steps = wrap.querySelectorAll(".status-step");
    var otherSelect = wrap.querySelector(".status-other");
    var pipeline = %s;

    function applyValue(val) {
        var idx = pipeline.indexOf(val);
        steps.forEach(function(el, i) {
            el.querySelector(".status-step-box").checked = (idx >= 0 && i <= idx);
        });
        otherSelect.value = (idx === -1) ? val : "";
    }

    steps.forEach(function(el) {
        el.addEventListener("click", function() {
            sel.value = el.getAttribute("data-code");
            applyValue(sel.value);
        });
    });

    otherSelect.addEventListener("change", function() {
        if (otherSelect.value) {
            sel.value = otherSelect.value;
            applyValue(sel.value);
        }
    });

    applyValue(sel.value);
})();
</script>
''' % (select_html, checklist_items, other_options, json.dumps(widget_id), pipeline_json)

        return mark_safe(html)
