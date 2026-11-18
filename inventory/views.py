from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import AbayaInventoryItemForm
from .models import AbayaInventoryItem, SaleTransaction


def blocked_in_demo(view):
    """In demo mode, visitors (non-staff users) can't change stock records."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if settings.DEMO_MODE and not request.user.is_staff:
            return HttpResponseForbidden(
                "Adding, editing and deleting items is turned off in demo mode."
            )
        return view(request, *args, **kwargs)
    return wrapper


def _record_sale(user, sku, raw_quantity):
    """
    Validate and record a sale for the item with the given SKU.

    Returns (True, None) on success or (False, error_message) on failure.
    The item row is locked so two cashiers can't sell the same last piece.
    """
    try:
        quantity = int(raw_quantity)
    except (TypeError, ValueError):
        return False, "Quantity must be a whole number."
    if quantity < 1:
        return False, "Quantity must be at least 1."

    with transaction.atomic():
        try:
            item = AbayaInventoryItem.objects.select_for_update().get(sku=sku)
        except AbayaInventoryItem.DoesNotExist:
            return False, "That item does not exist."

        if not item.is_active or item.stock_quantity == 0:
            return False, f"'{item.title}' is out of stock."
        if quantity > item.stock_quantity:
            return False, (
                f"Only {item.stock_quantity} left in stock for '{item.title}'. "
                f"Cannot sell {quantity}."
            )

        item.stock_quantity -= quantity
        if item.stock_quantity == 0:
            item.is_active = False
        item.user = user
        item.save()

        SaleTransaction.objects.create(
            item=item,
            quantity_sold=quantity,
            sale_price_per_item=item.selling_price,
            user=user,
        )
    return True, None


@login_required
def inventory_view(request):
    error = None
    if request.method == 'POST':
        ok, error = _record_sale(
            request.user,
            request.POST.get('sku', ''),
            request.POST.get('quantity', '1'),
        )
        if ok:
            return redirect('inventory:inventory')

    inventory = AbayaInventoryItem.objects.order_by('-updated_at')
    search_query = request.GET.get('search', '').strip()
    if search_query:
        inventory = inventory.filter(title__icontains=search_query)

    content = {
        'title': 'Inventory',
        'inventory': inventory,
        'error': error,
    }
    return render(request, 'inventory/inventory_dashboard.html', content)


@login_required
@blocked_in_demo
def inventory_add_view(request):
    form = AbayaInventoryItemForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.user = request.user
        item.save()
        return redirect('inventory:inventory')
    content = {
        'title': 'Add Inventory Item',
        'form': form,
    }
    return render(request, 'inventory/inventory_add.html', content)


@login_required
def inventory_item_view(request, sku):
    item = get_object_or_404(AbayaInventoryItem, sku=sku)
    content = {
        'title': f'Inventory Item: {item.title}',
        'item': item,
        'sale_transactions': item.sales.order_by('-sale_date'),
    }
    return render(request, 'inventory/inventory_item.html', content)


@login_required
@blocked_in_demo
@require_POST
def delete(request, sku):
    # POST-only so a link or image on another site can't delete stock.
    item = get_object_or_404(AbayaInventoryItem, sku=sku)
    item.is_active = False
    item.stock_quantity = 0
    item.user = request.user
    item.save()
    return redirect('inventory:inventory')


@login_required
@blocked_in_demo
def update_stock(request, sku):
    item = get_object_or_404(AbayaInventoryItem, sku=sku)
    if request.method == 'POST':
        form = AbayaInventoryItemForm(request.POST, instance=item)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.user = request.user
            updated.save()
            return redirect('inventory:inventory')
    else:
        form = AbayaInventoryItemForm(instance=item)
    content = {
        'title': f'Update Stock for {item.title}',
        'form': form,
        'item': item,
    }
    return render(request, 'inventory/inventory_update_stock.html', content)


@login_required
def server_log_view(request):
    content = {
        'title': 'Server Log',
        'inventory_items': AbayaInventoryItem.objects.order_by('-updated_at'),
        'sales_transactions': SaleTransaction.objects.select_related('item').order_by('-sale_date'),
    }
    return render(request, 'inventory/server_log.html', content)
