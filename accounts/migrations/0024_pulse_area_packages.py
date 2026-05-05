from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0023_add_token_version'),
    ]

    operations = [
        migrations.CreateModel(
            name='AreaPackage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='PulsePackage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pulses', models.PositiveIntegerField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('machine', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pulse_packages',
                    to='accounts.machine',
                )),
            ],
            options={'ordering': ['machine', 'pulses']},
        ),
    ]
