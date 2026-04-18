from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import PokemonProduct, Category, PokemonType, Era, CardSet
from users.models import User


class PokemonProductModelTests(TestCase):

    def setUp(self):
        self.era = Era.objects.create(code='B1', name='WotC Base Era')
        self.card_set = CardSet.objects.create(code='BS', name='Base Set', era=self.era)
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_pb_id_auto_generated(self):
        product = PokemonProduct.objects.create(
            name='Charizard Holo',
            category=self.category,
            card_set=self.card_set,
            rarity='holo_rare',
            pokedex_number=6,
            card_number=4,
            price=299.99,
            stock=5,
        )
        self.assertEqual(product.pb_id, 'PB-B1-BS-006-H-004')

    def test_sku_auto_generated(self):
        product = PokemonProduct.objects.create(
            name='Pikachu',
            category=self.category,
            card_set=self.card_set,
            rarity='common',
            pokedex_number=25,
            card_number=58,
            price=9.99,
            stock=10,
        )
        self.assertTrue(product.sku.startswith('PKB-'))

    def test_in_stock_property(self):
        product = PokemonProduct.objects.create(
            name='Blastoise',
            category=self.category,
            price=199.99,
            stock=0,
        )
        self.assertFalse(product.in_stock)
        product.stock = 1
        product.save()
        self.assertTrue(product.in_stock)

    def test_variant_override(self):
        product = PokemonProduct.objects.create(
            name='Charizard EX',
            category=self.category,
            card_set=self.card_set,
            rarity='ultra_rare',
            pokedex_number=6,
            card_number=12,
            variant_override='EX',
            price=499.99,
            stock=2,
        )
        self.assertEqual(product.pb_id, 'PB-B1-BS-006-EX-012')


class ProductAPITests(APITestCase):

    def setUp(self):
        self.era = Era.objects.create(code='B1', name='WotC Base Era')
        self.card_set = CardSet.objects.create(code='BS', name='Base Set', era=self.era)
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.user = User.objects.create_user(
            username='trainer', email='t@p.com', password='pikachu123'
        )
        self.admin = User.objects.create_superuser(
            username='admin', email='a@p.com', password='adminpass123'
        )
        self.product = PokemonProduct.objects.create(
            name='Charizard Holo',
            category=self.category,
            card_set=self.card_set,
            rarity='holo_rare',
            pokedex_number=6,
            card_number=4,
            price=299.99,
            stock=5,
        )

    def test_list_products_public(self):
        response = self.client.get(reverse('product-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_product_detail(self):
        response = self.client.get(reverse('product-detail', args=[self.product.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['pb_id'], 'PB-B1-BS-006-H-004')
        self.assertEqual(response.data['sku'], self.product.sku)

    def test_filter_by_rarity(self):
        response = self.client.get(reverse('product-list') + '?rarity=holo_rare')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_search_by_name(self):
        response = self.client.get(reverse('product-list') + '?search=charizard')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_create_product_requires_admin(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self._get_token(self.user)}"
        )
        response = self.client.post(reverse('product-list'), {
            'name': 'Pikachu', 'price': 9.99, 'stock': 10
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def _get_token(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        return str(RefreshToken.for_user(user).access_token)
