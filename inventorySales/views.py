from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from inventory.models import AbayaInventoryItem


@login_required
def home_view(request):
    inventory_items = AbayaInventoryItem.objects.all()
    content = {
        'title': 'Home',
        'inventory_items': inventory_items,
        'total_units': sum(item.stock_quantity for item in inventory_items),
        'low_stock_items': [item for item in inventory_items if item.is_low_stock],
    }
    return render(request, 'index.html', content)
