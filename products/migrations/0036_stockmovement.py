from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0035_era_symbol_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delta', models.IntegerField(help_text='Change in stock (+ loaded, - removed/wiped).')),
                ('stock_after', models.IntegerField()),
                ('source', models.CharField(choices=[('entry', 'Stock Entry'), ('played', 'Played copy added'), ('bundle', 'Bundle stock'), ('wipe', 'Wiped to 0'), ('opening', 'Opening balance')], default='entry', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_movements', to='products.pokemonproduct')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['product', 'created_at'], name='products_st_product_5f1c2e_idx')],
            },
        ),
    ]
