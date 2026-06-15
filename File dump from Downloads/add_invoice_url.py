with open('orders/urls.py', 'r') as f:
    content = f.read()

old = '    path("print/order/<int:order_id>/", views.print_order, name="print-order"),'
new = '''    path("print/order/<int:order_id>/", views.print_order, name="print-order"),
    path("print/invoice/<int:order_id>/", views.print_invoice, name="print-invoice"),'''

if old in content:
    content = content.replace(old, new)
    print("URL added")
else:
    print("NOT FOUND")

with open('orders/urls.py', 'w') as f:
    f.write(content)

# Also update admin to add invoice button
with open('orders/admin.py', 'r') as f:
    admin_content = f.read()

old2 = '''    def print_button(self, obj):
        if obj.pk:
            url = reverse('print-order', args=[obj.pk])
            return format_html(
                \'\'\'<a href="{}" target="_blank" style="
                    background:#ff6b35;color:#fff;padding:6px 14px;
                    border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px">
                    🖨 Print Pull Sheet
                </a>\'\'\',
                url
            )
        return '-'
    print_button.short_description = 'Print\''''

new2 = '''    def print_button(self, obj):
        if obj.pk:
            pull_url = reverse('print-order', args=[obj.pk])
            inv_url = reverse('print-invoice', args=[obj.pk])
            return format_html(
                \'\'\'<a href="{}" target="_blank" style="background:#ff6b35;color:#fff;padding:5px 12px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;margin-right:6px">🖨 Pull Sheet</a>
                <a href="{}" target="_blank" style="background:#1a1a24;color:#fff;padding:5px 12px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:12px;border:1px solid #555">📄 Invoice</a>\'\'\',
                pull_url, inv_url
            )
        return '-'
    print_button.short_description = 'Print\''''

if old2 in admin_content:
    admin_content = admin_content.replace(old2, new2)
    print("Admin button updated")
else:
    print("Admin button NOT FOUND")

with open('orders/admin.py', 'w') as f:
    f.write(admin_content)
