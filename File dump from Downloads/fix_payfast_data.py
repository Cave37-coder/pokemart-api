with open('payments/views.py', 'r') as f:
    content = f.read()

old = """        data = {
            'merchant_id':      settings.PAYFAST_MERCHANT_ID,
            'merchant_key':     settings.PAYFAST_MERCHANT_KEY,
            'return_url':       f'{site_url}/orders/{order.id}?payment=success',
            'cancel_url':       f'{site_url}/orders/{order.id}?payment=cancelled',
            'notify_url':       f'{api_url}/api/payments/itn/',
            'name_first':       request.user.first_name or request.user.username,
            'name_last':        request.user.last_name or '',
            'email_address':    request.user.email,
            'm_payment_id':     str(order.id),
            'amount':           f'{order.total_price:.2f}',
            'item_name':        f'PokeBulk SA Order #{order.id}',
        }

        # Remove empty values
        data = {k: v for k, v in data.items() if str(v).strip() != ''}

        passphrase = getattr(settings, 'PAYFAST_PASSPHRASE', '')
        signature = generate_payfast_signature(data, passphrase)
        data['signature'] = signature

        params = urllib.parse.urlencode(data)
        redirect_url = f'{payfast_url}?{params}'"""

new = """        name_first = (request.user.first_name or request.user.username or '').strip()
        name_last  = (request.user.last_name or '').strip()
        email      = (request.user.email or '').strip()

        data = {}
        data['merchant_id']   = str(settings.PAYFAST_MERCHANT_ID).strip()
        data['merchant_key']  = str(settings.PAYFAST_MERCHANT_KEY).strip()
        data['return_url']    = f'{site_url}/orders/{order.id}?payment=success'
        data['cancel_url']    = f'{site_url}/orders/{order.id}?payment=cancelled'
        data['notify_url']    = f'{api_url}/api/payments/itn/'
        if name_first:
            data['name_first'] = name_first
        if name_last:
            data['name_last']  = name_last
        if email:
            data['email_address'] = email
        data['m_payment_id']  = str(order.id)
        data['amount']        = f'{order.total_price:.2f}'
        data['item_name']     = f'PokeBulk Order #{order.id}'

        passphrase = getattr(settings, 'PAYFAST_PASSPHRASE', '')
        signature = generate_payfast_signature(data, passphrase)
        data['signature'] = signature

        params = urllib.parse.urlencode(data, quote_via=urllib.parse.quote)
        redirect_url = f'{payfast_url}?{params}'"""

if old in content:
    content = content.replace(old, new)
    print("Done")
else:
    print("NOT FOUND")

with open('payments/views.py', 'w') as f:
    f.write(content)
