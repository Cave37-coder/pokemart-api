import hashlib
import urllib.parse
import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from orders.models import Order, OrderTracking


def generate_payfast_signature(data: dict, passphrase: str = '') -> str:
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
    return hashlib.md5(payload.encode('utf-8')).hexdigest()


class PayFastInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in ('pending', 'payment_failed'):
            return Response({'error': 'Order already paid or processing'}, status=status.HTTP_400_BAD_REQUEST)

        sandbox = getattr(settings, 'PAYFAST_SANDBOX', False)
        payfast_url = (
            'https://sandbox.payfast.co.za/eng/process'
            if sandbox else
            'https://www.payfast.co.za/eng/process'
        )

        site_url = getattr(settings, 'SITE_URL', 'https://pokebulk.co.za')
        api_url  = getattr(settings, 'API_URL',  'https://pokemart-api-production.up.railway.app')

        name_first = (request.user.first_name or request.user.username or '').strip()
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
        redirect_url = f'{payfast_url}?{params}'

        return Response({
            'redirect_url': redirect_url,
            'order_id':     order.id,
            'amount':       str(order.total_price),
        })


@method_decorator(csrf_exempt, name='dispatch')
class PayFastITNView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        itn_data = request.POST.dict()
        payment_status = itn_data.get('payment_status')
        m_payment_id   = itn_data.get('m_payment_id')
        pf_payment_id  = itn_data.get('pf_payment_id', '')

        sandbox = getattr(settings, 'PAYFAST_SANDBOX', False)
        validate_url = (
            'https://sandbox.payfast.co.za/eng/query/validate'
            if sandbox else
            'https://www.payfast.co.za/eng/query/validate'
        )

        try:
            validate_response = requests.post(validate_url, data=itn_data, timeout=10)
            if validate_response.text != 'VALID':
                if not sandbox:
                    return Response(status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            if not sandbox:
                return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id=m_payment_id)
        except Order.DoesNotExist:
            return Response(status=status.HTTP_200_OK)

        if payment_status == 'COMPLETE':
            order.status = 'pending'
            order.stripe_payment_intent = pf_payment_id
            order.save()
            OrderTracking.objects.create(
                order=order,
                status='pending',
                note=f'Payment received via PayFast. PF Payment ID: {pf_payment_id}',
            )
        elif payment_status == 'FAILED':
            order.status = 'cancelled'
            order.save()
            OrderTracking.objects.create(
                order=order,
                status='cancelled',
                note='Payment failed via PayFast.',
            )

        return Response(status=status.HTTP_200_OK)
