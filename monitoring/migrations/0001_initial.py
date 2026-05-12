import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Agent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('secret_key', models.CharField(max_length=128)),
                ('ip_address', models.GenericIPAddressField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='GlobalConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.IntegerField(default=1)),
                ('config', models.JSONField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='NetworkScanSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=False, verbose_name='Автосканирование включено')),
                ('interval_minutes', models.PositiveIntegerField(default=5, verbose_name='Интервал (минуты)')),
            ],
            options={
                'verbose_name': 'Настройки сканирования сети',
                'verbose_name_plural': 'Настройки сканирования сети',
            },
        ),
        migrations.CreateModel(
            name='NotificationTarget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название')),
                ('target_type', models.CharField(choices=[('telegram', 'Telegram Bot'), ('discord', 'Discord Bot')], max_length=20, verbose_name='Тип бота')),
                ('token', models.CharField(max_length=255, verbose_name='Токен бота')),
                ('channels', models.JSONField(default=list, verbose_name='ID каналов/чатов')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлен')),
            ],
            options={
                'verbose_name': 'Получатель уведомлений',
                'verbose_name_plural': 'Получатели уведомлений',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AgentConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('override', models.JSONField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('agent', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='monitoring.agent')),
            ],
        ),
        migrations.CreateModel(
            name='AlertRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название правила')),
                ('rule_type', models.CharField(choices=[('metric', 'Метрики агента'), ('host', 'Хосты сети')], default='metric', max_length=10)),
                ('is_active', models.BooleanField(default=True, verbose_name='Активно')),
                ('cooldown_minutes', models.IntegerField(default=5, verbose_name='Перерыв между алертами (мин)')),
                ('last_triggered', models.DateTimeField(blank=True, null=True, verbose_name='Последний алерт')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('agent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='monitoring.agent', verbose_name='Агент')),
            ],
            options={
                'verbose_name': 'Правило алерта',
                'verbose_name_plural': 'Правила алертов',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AlertCondition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('condition_type', models.CharField(choices=[('metric', 'Метрика'), ('host', 'Хост')], default='metric', max_length=10)),
                ('metric_name', models.CharField(blank=True, max_length=100, null=True)),
                ('host_field', models.CharField(blank=True, choices=[('port', 'Открытый порт'), ('online', 'Онлайн'), ('mac', 'MAC-адрес'), ('ip', 'IP-адрес'), ('trusted', 'Доверенный')], help_text='Поле хоста: port, online, mac, ip, trusted', max_length=50, null=True)),
                ('operator', models.CharField(choices=[('>', '> (больше)'), ('<', '< (меньше)'), ('>=', '>= (больше или равно)'), ('<=', '<= (меньше или равно)'), ('==', '== (равно)'), ('!=', '!= (не равно)'), ('in', 'среди'), ('not_in', 'не среди')], max_length=20)),
                ('threshold', models.FloatField(blank=True, null=True)),
                ('value_str', models.CharField(blank=True, max_length=255, null=True, verbose_name='Значение (строка)')),
                ('is_active', models.BooleanField(default=True)),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conditions', to='monitoring.alertrule')),
            ],
            options={
                'verbose_name': 'Условие алерта',
                'verbose_name_plural': 'Условия алертов',
            },
        ),
        migrations.CreateModel(
            name='NetworkHost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(unique=True)),
                ('mac_address', models.CharField(blank=True, max_length=17, null=True)),
                ('hostname', models.CharField(blank=True, max_length=255, null=True)),
                ('os_info', models.CharField(blank=True, max_length=255, null=True, verbose_name='ОС')),
                ('manufacturer', models.CharField(blank=True, max_length=255, null=True, verbose_name='Производитель (MAC OUI)')),
                ('device_type', models.CharField(choices=[('unknown', 'Неизвестно'), ('router', 'Маршрутизатор'), ('switch', 'Коммутатор'), ('server', 'Сервер'), ('workstation', 'Рабочая станция'), ('printer', 'Принтер'), ('iot', 'IoT'), ('other', 'Другое')], default='unknown', max_length=20, verbose_name='Тип устройства')),
                ('ports_info', models.JSONField(blank=True, default=dict, verbose_name='Порты (последнее сканирование)')),
                ('notes', models.TextField(blank=True, verbose_name='Заметки')),
                ('is_trusted', models.BooleanField(default=False)),
                ('last_seen', models.DateTimeField(blank=True, null=True)),
                ('last_online', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('agent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='monitoring.agent')),
            ],
            options={
                'verbose_name': 'Сетевой хост',
                'verbose_name_plural': 'Сетевые хосты',
                'ordering': ['ip_address'],
            },
        ),
        migrations.AddField(
            model_name='alertrule',
            name='host',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='monitoring.networkhost', verbose_name='Хост'),
        ),
        migrations.CreateModel(
            name='AlertAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(choices=[('telegram', 'Отправить в Telegram'), ('discord', 'Отправить в Discord')], max_length=20, verbose_name='Тип действия')),
                ('message', models.TextField(verbose_name='Сообщение')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активно')),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actions', to='monitoring.alertrule', verbose_name='Правило')),
                ('target', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='monitoring.notificationtarget', verbose_name='Бот-получатель')),
            ],
            options={
                'verbose_name': 'Действие алерта',
                'verbose_name_plural': 'Действия алертов',
            },
        ),
        migrations.CreateModel(
            name='UserDashboard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.JSONField(default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='dashboard', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Metric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField()),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=50)),
                ('value', models.FloatField()),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='metrics', to='monitoring.agent')),
            ],
            options={
                'ordering': ['-timestamp'],
                'indexes': [models.Index(fields=['agent', 'timestamp'], name='monitoring__agent_i_2119b8_idx'), models.Index(fields=['name'], name='monitoring__name_2c6ccf_idx')],
            },
        ),
    ]
