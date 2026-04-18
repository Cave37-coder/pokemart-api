from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import User
from products.models import PokemonProduct, Category, Era, CardSet
from orders.models import Cart, CartItem, Order


class CartTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='ash', email='ash@pokemon.com', password='pikachu123'
        )
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.product = PokemonProduct.objects.create(
            name='Charizard',
            category=self.category,
            price=299.99,
            stock=5,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(RefreshToken.for_user(self.user).access_token)}"
        )

    def test_view_empty_cart(self):
        response = self.client.get(reverse('cart'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 0)

    def test_add_item_to_cart(self):
        response = self.client.post(reverse('cart-add'), {
            'product_id': self.product.id,
            'quantity': 2
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['total'], '599.98')

    def test_add_item_exceeds_stock(self):
        response = self.client.post(reverse('cart-add'), {
            'product_id': self.product.id,
            'quantity': 99
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cart_requires_auth(self):
        self.client.credentials()
        response = self.client.get(reverse('cart'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CheckoutTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='ash', email='ash@pokemon.com', password='pikachu123'
        )
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.product = PokemonProduct.objects.create(
            name='Charizard',
            category=self.category,
            price=299.99,
            stock=5,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(RefreshToken.for_user(self.user).access_token)}"
        )

    def test_checkout_creates_order_and_decrements_stock(self):
        self.client.post(reverse('cart-add'), {
            'product_id': self.product.id,
            'quantity': 2
        }, format='json')
        response = self.client.post(reverse('checkout'), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(response.data['total_price'], '599.98')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_checkout_empty_cart(self):
        response = self.client.post(reverse('checkout'), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_appears_in_history(self):
        self.client.post(reverse('cart-add'), {
            'product_id': self.product.id, 'quantity': 1
        }, format='json')
        self.client.post(reverse('checkout'), format='json')
        response = self.client.get(reverse('order-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)