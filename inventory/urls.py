from django.urls import path
from . import views

app_name = 'inventory'
urlpatterns = [
    path('', views.inventory_view, name='inventory'),
    path('server-log/', views.server_log_view, name='server_log'),
    path('add/', views.inventory_add_view, name='Add_inventory'),
    path('update-stock/<slug:sku>/', views.update_stock, name='update_stock'),
    path('<slug:sku>/', views.inventory_item_view, name='inventory_item'),
    path('delete/<slug:sku>/', views.delete, name='delete'),
]