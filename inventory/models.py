import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify


class Size(models.Model):
    """
    A size that shop staff can manage in the admin.
    Items point to one Size, so adding a size needs no code change.
    """
    label = models.CharField(max_length=20, unique=True, help_text="Shown to staff, e.g. 54 or M")
    measurement = models.CharField(
        max_length=100, blank=True,
        help_text="Optional fit guide, e.g. Height 5'3\" - 5'5\"",
    )
    sort_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first")
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide from new items")

    class Meta:
        ordering = ['sort_order', 'label']

    def __str__(self):
        return self.label


class AbayaInventoryItem(models.Model):
    """
    A single-class system that serves as both the product definition
    and the specific physical stock unit (SKU) for the inventory.
    """
    # CORE APPAREL DETAILS
    title = models.CharField(max_length=255, help_text="e.g., Elegant Lace Nida Abaya")

    # Make blank=True so the system can generate this automatically
    sku = models.SlugField(
        max_length=64,
        unique=True,
        blank=True,
        help_text="Unique Stock Keeping Unit (Auto-generated slug if left blank)",
    )

    brand_name = models.CharField(max_length=100, help_text="e.g., Al-Karam, LAAM, or Self-Made")
    color_name = models.CharField(max_length=50, help_text="e.g., Midnight Black, Rose Gold, Sage Green")
    material = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Nida, Korean Crepe, Linen")
    description = models.TextField(blank=True, null=True)

    # SIZING: each item points to a Size row managed in the admin
    size = models.ForeignKey(
        Size,
        on_delete=models.PROTECT,  # can't delete a size that items still use
        related_name='items',
        help_text="Garment size, managed under Sizes in the admin",
    )

    # INVENTORY & FINANCIAL TRACKING
    stock_quantity = models.PositiveIntegerField(default=0, help_text="Current physical items in storage")
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="How much you paid to manufacture/source it",
    )
    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="The retail price listed to clients",
    )

    # SYSTEM TIMESTAMPS & STATUS
    is_active = models.BooleanField(default=True, help_text="Uncheck to temporarily hide from stock views")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who added or last updated this item",
    )

    class Meta:
        unique_together = ('title', 'brand_name', 'size', 'color_name')
        verbose_name = "Abaya Inventory Item"
        verbose_name_plural = "Abaya Inventory Items"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= settings.LOW_STOCK_THRESHOLD

    def send_low_stock_alert(self):
        if self.is_low_stock and settings.ADMIN_EMAIL:
            subject = f"Low Stock Alert: {self.title} (SKU: {self.sku})"
            message = f"The stock for {self.title} (SKU: {self.sku}) is low. Current quantity: {self.stock_quantity}."
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [settings.ADMIN_EMAIL])
            except Exception as e:
                # log it instead of letting it bubble up and break the save
                print(f"Failed to send low stock alert: {e}")

    @property
    def potential_profit(self):
        """Calculates profit margins directly for your dashboard reports."""
        return self.selling_price - self.cost_price

    @property
    def inventory_value(self):
        """Calculates total tied-up financial capital in this specific item pool."""
        return self.stock_quantity * self.cost_price

    def save(self, *args, **kwargs):
        """Automates SKU generation if left blank before saving to database."""
        if not self.sku:
            # Generates a clean 8-character unique uppercase string suffix
            unique_suffix = uuid.uuid4().hex[:8].upper()
            clean_brand = slugify(self.brand_name).replace("-", "").upper()[:3]
            clean_title = slugify(self.title).replace("-", "").upper()[:3]
            size_part = slugify(self.size.label).upper()
            self.sku = f"{clean_brand}-{clean_title}-{size_part}-{unique_suffix}"

        if self.pk:
            old_quantity = type(self).objects.filter(pk=self.pk).values_list("stock_quantity", flat=True).first()
            crossed_threshold = (
                old_quantity is not None
                and old_quantity > settings.LOW_STOCK_THRESHOLD
                and self.stock_quantity <= settings.LOW_STOCK_THRESHOLD
            )
        else:
            crossed_threshold = self.stock_quantity <= settings.LOW_STOCK_THRESHOLD
        super().save(*args, **kwargs)
        if crossed_threshold:
            self.send_low_stock_alert()

    def __str__(self):
        return f"[{self.sku}] {self.brand_name} - {self.title} (Size {self.size.label} / {self.color_name})"


class SaleTransaction(models.Model):
    """
    Represents a single sale transaction for an AbayaInventoryItem.
    """
    item = models.ForeignKey(AbayaInventoryItem, on_delete=models.CASCADE, related_name='sales')
    quantity_sold = models.PositiveIntegerField(validators=[MinValueValidator(1)], help_text="Number of items sold in this transaction")
    sale_price_per_item = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at which each item was sold")
    total_sale_value = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    sale_date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, help_text="User who processed the sale")

    class Meta:
        verbose_name = "Sale Transaction"
        verbose_name_plural = "Sale Transactions"

    def save(self, *args, **kwargs):
        """Calculates total sale value before saving."""
        self.total_sale_value = self.quantity_sold * self.sale_price_per_item
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale of {self.quantity_sold} x {self.item.title} on {self.sale_date.strftime('%Y-%m-%d %H:%M:%S')}"
