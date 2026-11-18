from django import forms
from django.db.models import Q

from .models import AbayaInventoryItem, Size


class AbayaInventoryItemForm(forms.ModelForm):
    class Meta:
        model = AbayaInventoryItem
        fields = ['sku', 'title', 'description', 'stock_quantity', 'selling_price', 'cost_price',
                  'size', 'color_name', 'brand_name', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Offer only active sizes, but keep the item's current size so editing still validates.
        current_size_id = self.instance.size_id if self.instance and self.instance.pk else None
        self.fields['size'].queryset = Size.objects.filter(
            Q(is_active=True) | Q(pk=current_size_id)
        )
        self.fields['size'].empty_label = "Choose a size"
