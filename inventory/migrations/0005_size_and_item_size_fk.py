"""
Replace the hardcoded integer size on items with a Size table.

Steps:
1. Create the Size table.
2. Add a nullable foreign key, size_fk, next to the old integer field.
3. Seed the standard sizes (50-62) and point every existing item at the
   matching Size row, creating any missing rows along the way.
4. Drop the old integer field and rename size_fk to size.

This migration is forward-only: once the old column is dropped, the
integer sizes can't be rebuilt automatically. Back up the database first.
"""
import django.db.models.deletion
from django.db import migrations, models

STANDARD_SIZES = {
    50: "Height 4'11\" - 5'1\"",
    52: "Height 5'1\" - 5'3\"",
    54: "Height 5'3\" - 5'5\"",
    56: "Height 5'5\" - 5'7\"",
    58: "Height 5'7\" - 5'9\"",
    60: "Height 5'9\" - 6'0\"",
    62: "Height 6'0\" - 6'2\"",
}


def copy_sizes_forward(apps, schema_editor):
    Size = apps.get_model('inventory', 'Size')
    Item = apps.get_model('inventory', 'AbayaInventoryItem')

    sizes_by_label = {}
    for order, (length, fit) in enumerate(STANDARD_SIZES.items()):
        size, _ = Size.objects.get_or_create(
            label=str(length),
            defaults={'measurement': fit, 'sort_order': order},
        )
        sizes_by_label[str(length)] = size

    for item in Item.objects.all():
        label = str(item.size)  # old integer value
        if label not in sizes_by_label:
            sizes_by_label[label], _ = Size.objects.get_or_create(
                label=label,
                defaults={'sort_order': 1000 + int(item.size)},
            )
        item.size_fk = sizes_by_label[label]
        item.save(update_fields=['size_fk'])


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_abayainventoryitem_user_saletransaction_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='Size',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(help_text='Shown to staff, e.g. 54 or M', max_length=20, unique=True)),
                ('measurement', models.CharField(blank=True, help_text="Optional fit guide, e.g. Height 5'3\" - 5'5\"", max_length=100)),
                ('sort_order', models.PositiveIntegerField(default=0, help_text='Lower numbers appear first')),
                ('is_active', models.BooleanField(default=True, help_text='Uncheck to hide from new items')),
            ],
            options={'ordering': ['sort_order', 'label']},
        ),
        # The unique constraint includes the old field, so drop it while the columns change.
        migrations.AlterUniqueTogether(name='abayainventoryitem', unique_together=set()),
        migrations.AddField(
            model_name='abayainventoryitem',
            name='size_fk',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='items',
                to='inventory.size',
            ),
        ),
        migrations.RunPython(copy_sizes_forward, migrations.RunPython.noop),
        migrations.RemoveField(model_name='abayainventoryitem', name='size'),
        migrations.RenameField(model_name='abayainventoryitem', old_name='size_fk', new_name='size'),
        migrations.AlterField(
            model_name='abayainventoryitem',
            name='size',
            field=models.ForeignKey(
                help_text='Garment size, managed under Sizes in the admin',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='items',
                to='inventory.size',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='abayainventoryitem',
            unique_together={('title', 'brand_name', 'size', 'color_name')},
        ),
    ]
