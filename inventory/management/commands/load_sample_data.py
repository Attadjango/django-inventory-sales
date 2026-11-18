from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import AbayaInventoryItem, Size
from inventory.views import _record_sale

SAMPLE_BRANDS = ['Noor Atelier', 'Safa Textiles', 'Rahat Fabrics']

# Fictional items. Each sold quantity is recorded as a sale after the stock is set,
# so the final stock figure is what visitors will see.
# (title, brand, colour, size label, final stock, cost, price, units already sold)
SAMPLE_ITEMS = [
    ('Pearl Nida Abaya', 'Noor Atelier', 'Midnight Black', '54', 6, '3500', '5200', 2),
    ('Embroidered Crepe Abaya', 'Noor Atelier', 'Sage Green', '56', 4, '4200', '6100', 1),
    ('Linen Blend Abaya', 'Safa Textiles', 'Sand Beige', '52', 3, '2800', '4100', 1),
    ('Chiffon Open Abaya', 'Safa Textiles', 'Rose Mauve', '58', 9, '3900', '5600', 3),
    ('Lace Trim Abaya', 'Rahat Fabrics', 'Navy Blue', '54', 0, '3600', '5300', 0),
    ('Classic Crepe Abaya', 'Rahat Fabrics', 'Charcoal', '60', 7, '3000', '4500', 0),
]


class Command(BaseCommand):
    help = (
        "Load six fictional sample items, a few past sales, and the demo visitor account. "
        "Refuses to run unless DJANGO_DEMO_MODE is on, unless --force is given."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Delete the existing sample items (and their sales) before loading.',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Allow running when demo mode is off. Use only on a throwaway database.',
        )

    def handle(self, *args, **options):
        if not settings.DEMO_MODE and not options['force']:
            raise CommandError(
                "Refusing to load sample data: demo mode is off. "
                "Set DJANGO_DEMO_MODE=True, or use --force on a throwaway database."
            )

        sample_qs = AbayaInventoryItem.objects.filter(brand_name__in=SAMPLE_BRANDS)
        with transaction.atomic():
            if sample_qs.exists():
                if not options['reset']:
                    raise CommandError("Sample data is already loaded. Use --reset to reload it.")
                deleted, _ = sample_qs.delete()
                self.stdout.write(f"Removed existing sample rows ({deleted} objects).")

            demo_user = self._ensure_demo_user()

            for title, brand, colour, size_label, final_stock, cost, price, sold in SAMPLE_ITEMS:
                item = AbayaInventoryItem.objects.create(
                    title=title,
                    brand_name=brand,
                    color_name=colour,
                    material='Nida',
                    description='Fictional sample item for the demo.',
                    size=Size.objects.get(label=size_label),
                    stock_quantity=final_stock + sold,
                    cost_price=Decimal(cost),
                    selling_price=Decimal(price),
                    is_active=(final_stock > 0),
                )
                if sold:
                    ok, error = _record_sale(demo_user, item.sku, sold)
                    if not ok:
                        raise CommandError(f"Could not record sample sale: {error}")

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(SAMPLE_ITEMS)} sample items and the demo account "
            f"'{settings.DEMO_USERNAME}'."
        ))

    def _ensure_demo_user(self):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=settings.DEMO_USERNAME)
        if not created and user.is_staff:
            raise CommandError(
                f"The user '{settings.DEMO_USERNAME}' is a staff account. "
                "Choose another DJANGO_DEMO_USERNAME."
            )
        user.is_staff = False
        user.is_superuser = False
        user.set_password(settings.DEMO_PASSWORD)
        user.save()
        return user
