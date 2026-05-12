from django.db import migrations

def create_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser(
            username='admin',
            email='',
            password='12345678'
        )

def remove_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='admin').delete()

class Migration(migrations.Migration):
    dependencies = [
        # Укажите вашу единственную начальную миграцию (обычно это ('monitoring', '0001_initial'))
        ('monitoring', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_admin, remove_admin),
    ]