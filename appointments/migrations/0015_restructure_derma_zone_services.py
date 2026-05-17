from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0014_add_derma_face_mapping'),
        ('accounts', '0028_add_doctor_medicine'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dermafacemappingzone',
            name='service',
        ),
        migrations.RemoveField(
            model_name='dermafacemappingline',
            name='zone',
        ),
        migrations.CreateModel(
            name='DermaFaceMappingZoneService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('zone', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zone_services', to='appointments.dermafacemappingzone')),
                ('service', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.service')),
            ],
        ),
        migrations.AddField(
            model_name='dermafacemappingline',
            name='zone_service',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='appointments.dermafacemappingzoneservice'),
        ),
    ]
