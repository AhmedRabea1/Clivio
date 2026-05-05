from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0024_pulse_area_packages'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='pulsepackage',
            name='machine',
        ),
        migrations.AddField(
            model_name='pulsepackage',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='areapackage',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterModelOptions(
            name='pulsepackage',
            options={'ordering': ['pulses']},
        ),
    ]
