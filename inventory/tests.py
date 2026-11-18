from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AbayaInventoryItem, SaleTransaction, Size

User = get_user_model()


def make_size(label='54', **overrides):
    return Size.objects.get_or_create(label=label, defaults=overrides)[0]


def make_item(**overrides):
    data = dict(
        title='Lace Abaya',
        brand_name='Al Karam',
        color_name='Black',
        size=make_size(),
        stock_quantity=10,
        cost_price=Decimal('10.00'),
        selling_price=Decimal('20.00'),
    )
    data.update(overrides)
    return AbayaInventoryItem.objects.create(**data)


class SaleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('clerk', 'clerk@example.com', 'Str0ng-pass-123')
        self.client.force_login(self.user)
        self.item = make_item(stock_quantity=3)

    def post_sale(self, quantity):
        return self.client.post(reverse('inventory:inventory'), {'sku': self.item.sku, 'quantity': quantity})

    def test_valid_sale_reduces_stock_and_records_transaction(self):
        self.post_sale(2)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 1)
        sale = SaleTransaction.objects.get()
        self.assertEqual(sale.quantity_sold, 2)
        self.assertEqual(sale.total_sale_value, Decimal('40.00'))
        self.assertEqual(sale.user, self.user)

    def test_selling_last_unit_deactivates_item(self):
        self.post_sale(3)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 0)
        self.assertFalse(self.item.is_active)

    def test_cannot_oversell(self):
        response = self.post_sale(5)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 3)
        self.assertEqual(SaleTransaction.objects.count(), 0)
        self.assertContains(response, 'Only 3 left in stock')

    def test_cannot_sell_out_of_stock_item(self):
        self.item.stock_quantity = 0
        self.item.is_active = False
        self.item.save()
        self.post_sale(1)
        self.assertEqual(SaleTransaction.objects.count(), 0)

    def test_rejects_non_numeric_and_zero_quantity(self):
        self.post_sale('abc')
        self.post_sale(0)
        self.post_sale(-4)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 3)
        self.assertEqual(SaleTransaction.objects.count(), 0)


class AccessTests(TestCase):
    def setUp(self):
        self.item = make_item()

    def test_pages_require_login(self):
        urls = [
            reverse('inventory:inventory'),
            reverse('inventory:Add_inventory'),
            reverse('inventory:server_log'),
            reverse('inventory:update_stock', args=[self.item.sku]),
            reverse('inventory:inventory_item', args=[self.item.sku]),
            reverse('home'),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('users:login'), response.url)

    def test_delete_requires_post(self):
        self.client.force_login(User.objects.create_user('clerk', 'c@example.com', 'Str0ng-pass-123'))
        self.client.get(reverse('inventory:delete', args=[self.item.sku]))
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)
        self.assertEqual(self.item.stock_quantity, 10)

    def test_missing_item_returns_404(self):
        self.client.force_login(User.objects.create_user('clerk', 'c@example.com', 'Str0ng-pass-123'))
        response = self.client.get(reverse('inventory:inventory_item', args=['NOPE']))
        self.assertEqual(response.status_code, 404)


class LoginRedirectTests(TestCase):
    def setUp(self):
        User.objects.create_user('clerk', 'c@example.com', 'Str0ng-pass-123')

    def test_external_next_url_is_ignored(self):
        response = self.client.post(reverse('users:login'), {
            'username': 'clerk', 'password': 'Str0ng-pass-123', 'next': 'https://evil.example.com/',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('inventory:inventory'))

    def test_internal_next_url_is_followed(self):
        response = self.client.post(reverse('users:login'), {
            'username': 'clerk', 'password': 'Str0ng-pass-123', 'next': reverse('inventory:server_log'),
        })
        self.assertEqual(response.url, reverse('inventory:server_log'))


class LowStockAlertTests(TestCase):
    @override_settings(ADMIN_EMAIL='owner@example.com')
    def test_alert_sent_when_crossing_threshold(self):
        item = make_item(stock_quantity=6)
        mail.outbox.clear()
        item.stock_quantity = 5
        item.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['owner@example.com'])

    @override_settings(ADMIN_EMAIL='owner@example.com')
    def test_no_repeat_alert_while_already_low(self):
        item = make_item(stock_quantity=4)
        mail.outbox.clear()
        item.stock_quantity = 3
        item.save()
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(ADMIN_EMAIL='')
    def test_no_alert_without_admin_email(self):
        item = make_item(stock_quantity=6)
        mail.outbox.clear()
        item.stock_quantity = 1
        item.save()
        self.assertEqual(len(mail.outbox), 0)


class SizeModelTests(TestCase):
    def test_item_sku_uses_size_label(self):
        item = make_item(size=make_size('XL'))
        self.assertIn('-XL-', item.sku)

    def test_size_with_spaces_gives_valid_sku(self):
        item = make_item(size=make_size('Extra Large'))
        self.assertIn('-EXTRA-LARGE-', item.sku)

    def test_size_in_use_cannot_be_deleted(self):
        from django.db.models import ProtectedError
        size = make_size('60')
        make_item(size=size)
        with self.assertRaises(ProtectedError):
            size.delete()

    def test_inactive_size_hidden_from_item_form_but_kept_when_editing(self):
        from .forms import AbayaInventoryItemForm
        retired = make_size('48', is_active=False)
        current = make_size('56')
        item = make_item(size=retired)

        new_form = AbayaInventoryItemForm()
        self.assertNotIn(retired, new_form.fields['size'].queryset)
        self.assertIn(current, new_form.fields['size'].queryset)

        edit_form = AbayaInventoryItemForm(instance=item)
        self.assertIn(retired, edit_form.fields['size'].queryset)

    def test_size_admin_page_loads_for_staff(self):
        admin_user = User.objects.create_superuser('boss', 'boss@example.com', 'Str0ng-pass-123')
        self.client.force_login(admin_user)
        self.assertEqual(self.client.get('/admin/inventory/size/').status_code, 200)


from django.core.management import call_command
from django.core.management.base import CommandError


@override_settings(DEMO_MODE=True, DEMO_USERNAME='demo', DEMO_PASSWORD='demo-pass-2026')
class DemoModeTests(TestCase):
    def setUp(self):
        self.visitor = User.objects.create_user('demo', 'demo@example.com', 'demo-pass-2026')
        self.item = make_item(stock_quantity=5)
        self.client.force_login(self.visitor)

    def test_visitor_can_record_sale(self):
        self.client.post(reverse('inventory:inventory'), {'sku': self.item.sku, 'quantity': 2})
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 3)

    def test_visitor_cannot_add_edit_or_delete(self):
        self.assertEqual(self.client.get(reverse('inventory:Add_inventory')).status_code, 403)
        self.assertEqual(self.client.get(reverse('inventory:update_stock', args=[self.item.sku])).status_code, 403)
        self.assertEqual(self.client.post(reverse('inventory:delete', args=[self.item.sku])).status_code, 403)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_staff_keep_full_access_in_demo_mode(self):
        staff = User.objects.create_user('owner', 'o@example.com', 'Str0ng-pass-123', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse('inventory:Add_inventory')).status_code, 200)

    def test_dashboard_hides_editing_buttons_and_shows_banner(self):
        response = self.client.get(reverse('inventory:inventory'))
        self.assertContains(response, 'Demo mode.')
        self.assertNotContains(response, 'Update Stock')
        self.assertNotContains(response, 'Add Inventory')

    def test_login_page_shows_demo_credentials(self):
        self.client.logout()
        response = self.client.get(reverse('users:login'))
        self.assertContains(response, 'demo-pass-2026')

    @override_settings(DEMO_MODE=False)
    def test_login_page_hides_credentials_outside_demo(self):
        response = self.client.get(reverse('users:login'))
        self.assertNotContains(response, 'Demo login')

    @override_settings(DEMO_MODE=False)
    def test_no_restrictions_outside_demo(self):
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(reverse('inventory:Add_inventory')).status_code, 200)


@override_settings(DEMO_MODE=True, DEMO_USERNAME='demo', DEMO_PASSWORD='demo-pass-2026')
class LoadSampleDataTests(TestCase):
    def test_loads_six_items_and_sales(self):
        call_command('load_sample_data', stdout=open('/dev/null', 'w'))
        self.assertEqual(AbayaInventoryItem.objects.filter(brand_name__in=['Noor Atelier', 'Safa Textiles', 'Rahat Fabrics']).count(), 6)
        self.assertEqual(sum(SaleTransaction.objects.values_list('quantity_sold', flat=True)), 7)
        self.assertTrue(User.objects.get(username='demo').check_password('demo-pass-2026'))
        self.assertFalse(User.objects.get(username='demo').is_staff)

    def test_refuses_to_run_twice_without_reset(self):
        call_command('load_sample_data', stdout=open('/dev/null', 'w'))
        with self.assertRaises(CommandError):
            call_command('load_sample_data', stdout=open('/dev/null', 'w'))

    def test_reset_reloads_cleanly(self):
        call_command('load_sample_data', stdout=open('/dev/null', 'w'))
        call_command('load_sample_data', '--reset', stdout=open('/dev/null', 'w'))
        self.assertEqual(AbayaInventoryItem.objects.count(), 6)
        self.assertEqual(sum(SaleTransaction.objects.values_list('quantity_sold', flat=True)), 7)

    def test_leaves_real_items_alone(self):
        call_command('load_sample_data', stdout=open('/dev/null', 'w'))
        real = make_item(title='Real Shop Item', brand_name='Real Brand', stock_quantity=2)
        call_command('load_sample_data', '--reset', stdout=open('/dev/null', 'w'))
        self.assertTrue(AbayaInventoryItem.objects.filter(pk=real.pk).exists())

    @override_settings(DEMO_MODE=False)
    def test_refuses_outside_demo_mode_without_force(self):
        with self.assertRaises(CommandError):
            call_command('load_sample_data', stdout=open('/dev/null', 'w'))
