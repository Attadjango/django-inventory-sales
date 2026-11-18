from django.contrib import admin

from .models import AbayaInventoryItem, SaleTransaction, Size


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ('label', 'measurement', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('label', 'measurement')


@admin.register(AbayaInventoryItem)
class AbayaInventoryItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'brand_name', 'size', 'color_name', 'stock_quantity', 'is_active')
    list_filter = ('size', 'is_active')
    search_fields = ('title', 'brand_name', 'sku')


admin.site.register(SaleTransaction)
