from django.db import migrations

def seed(apps, schema_editor):
    AssistantRole = apps.get_model('accounts', 'AssistantRole')
    for role in ['view_assistant', 'add_assistant', 'edit_assistant', 'delete_assistant']:
        AssistantRole.objects.get_or_create(role_name=role)

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0021_add_assistant_roles'),
    ]
    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
