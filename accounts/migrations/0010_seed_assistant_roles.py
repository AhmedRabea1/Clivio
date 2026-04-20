from django.db import migrations

ROLES = [
    'view_inventory', 'edit_inventory', 'add_inventory', 'delete_inventory',
    'view_config', 'edit_config',
    'view_doctor', 'add_doctor', 'edit_doctor', 'delete_doctor',
    'view_branch', 'add_branch', 'edit_branch', 'delete_branch',
    'view_patient', 'add_patient', 'edit_patient', 'delete_patient',
]

def seed_roles(apps, schema_editor):
    AssistantRole = apps.get_model('accounts', 'AssistantRole')
    for role in ROLES:
        AssistantRole.objects.get_or_create(role_name=role)

def unseed_roles(apps, schema_editor):
    apps.get_model('accounts', 'AssistantRole').objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [('accounts', '0009_add_assistant_role')]
    operations = [migrations.RunPython(seed_roles, unseed_roles)]
