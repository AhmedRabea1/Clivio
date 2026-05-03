from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0006_alter_reservation_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='mobile_number',
            field=models.CharField(max_length=20),
        ),
        migrations.AddField(
            model_name='patient',
            name='is_primary',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='patient',
            name='primary_patient',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='family_members',
                to='appointments.patient',
            ),
        ),
    ]
