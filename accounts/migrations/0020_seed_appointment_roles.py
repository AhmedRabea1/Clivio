from django.db import migrations

def seed_appointment_roles(apps, schema_editor):
    AssistantRole = apps.get_model('accounts', 'AssistantRole')
    new_roles = [
        'view_appointment',
        'add_appointment',
        'edit_appointment',
        'delete_appointment',
    ]
    for role in new_roles:
        AssistantRole.objects.get_or_create(role_name=role)

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0019_add_appointment_roles'),
    ]
    operations = [
        migrations.RunPython(seed_appointment_roles, migrations.RunPython.noop),
    ]
