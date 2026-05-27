# Fix PayFast signature generation in payments/views.py
with open('payments/views.py', 'r') as f:
    content = f.read()

old = '''def generate_payfast_signature(data: dict, passphrase: str = '') -> str:
    payload = '&'.join(
        f'{k}={urllib.parse.quote_plus(str(v))}'
        for k, v in data.items()
        if v != ''
    )
    # Only append passphrase if it is actually set
    if passphrase and passphrase.strip():
        payload += f'&passphrase={urllib.parse.quote_plus(passphrase.strip())}'
    return hashlib.md5(payload.encode()).hexdigest()'''

new = '''def generate_payfast_signature(data: dict, passphrase: str = '') -> str:
    # PayFast requires specific encoding - spaces as + not %20, no encoding of certain chars
    def pf_encode(val):
        return urllib.parse.quote_plus(str(val).strip())
    
    payload = '&'.join(
        f'{k}={pf_encode(v)}'
        for k, v in data.items()
        if str(v).strip() != ''
    )
    if passphrase and passphrase.strip():
        payload += f'&passphrase={pf_encode(passphrase.strip())}'
    return hashlib.md5(payload.encode('utf-8')).hexdigest()'''

if old in content:
    content = content.replace(old, new)
    print("Signature function updated")
else:
    print("NOT FOUND - checking current function")
    # Show what's there
    start = content.find('def generate_payfast')
    print(content[start:start+500])

with open('payments/views.py', 'w') as f:
    f.write(content)
