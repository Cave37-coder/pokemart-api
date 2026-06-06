from django.urls import path
from products.views import stock_entry, stock_update, stock_wipe, stock_print

urlpatterns = [
    path('entry/', stock_entry, name='stock_entry'),
    path('entry/update/', stock_update, name='stock_update'),
    path('entry/wipe/', stock_wipe, name='stock_wipe'),
    path('print/', stock_print, name='stock_print'),
]
