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
from orders.models import Order


def generate_payfast_signature(data, passphrase=''):
    # Build query string from data
    payload = '&'.join([f'{k}={urllib.parse.quote_plus(str(v))}' for k, v in data.items() if v != ''])
    if passphrase:
        payload += f'&passphrase={urllib.parse.quote_plus(passphrase)}'
    return hashlib.md5(payload.encode()).hexdigest()


class PayFastInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        if order.status != 'pending':
            return Response({'error': 'Order already paid'}, status=status.HTTP_400_BAD_REQUEST)

        if settings.PAYFAST_SANDBOX:
            payfast_url = 'https://sandbox.payfast.co.za/eng/process'
        else:
            payfast_url = 'https://www.payfast.co.za/eng/process'

        data = {
            'merchant_id': settings.PAYFAST_MERCHANT_ID,
            'merchant_key': settings.PAYFAST_MERCHANT_KEY,
            'return_url': 'http://localhost:3000/payment/success',
            'cancel_url': 'http://localhost:3000/payment/cancel',
            'notify_url': 'http://your-domain.com/api/payments/itn/',
            'name_first': request.user.first_name or request.user.username,
            'email_address': request.user.email,
            'm_payment_id': str(order.id),
            'amount': str(order.total_price),
            'item_name': f'PokeMart Order #{order.id}',
        }

        signature = generate_payfast_signature(data, settings.PAYFAST_PASSPHRASE)
        data['signature'] = signature

        # Build the redirect URL
        params = urllib.parse.urlencode(data)
        redirect_url = f'{payfast_url}?{params}'

        return Response({
            'redirect_url': redirect_url,
            'order_id': order.id,
            'amount': str(order.total_price),
        })


@method_decorator(csrf_exempt, name='dispatch')
class PayFastITNView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        itn_data = request.POST.dict()
        payment_status = itn_data.get('payment_status')
        m_payment_id = itn_data.get('m_payment_id')

        # Verify with PayFast servers
        if settings.PAYFAST_SANDBOX:
            validate_url = 'https://sandbox.payfast.co.za/eng/query/validate'
        else:
            validate_url = 'https://www.payfast.co.za/eng/query/validate'

        try:
            validate_response = requests.post(validate_url, data=itn_data)
            if validate_response.text != 'VALID':
                return Response(status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Update order status
        try:
            order = Order.objects.get(id=m_payment_id)
            if payment_status == 'COMPLETE':
                order.status = 'paid'
                order.stripe_payment_intent = itn_data.get('pf_payment_id', '')
                order.save()
        except Order.DoesNotExist:
            pass

        return Response(status=status.HTTP_200_OK)
