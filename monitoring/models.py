import uuid, requests, fnmatch
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.utils.timezone import localtime


class Agent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    secret_key = models.CharField(max_length=128)
    ip_address = models.GenericIPAddressField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    @property
    def is_online(self):
        if not self.last_seen:
            return False
        from django.utils import timezone
        from datetime import timedelta
        return self.last_seen >= timezone.now() - timedelta(minutes=5)

    def __str__(self):
        return self.name


class Metric(models.Model):
    agent = models.ForeignKey(
        "Agent",
        on_delete=models.CASCADE,
        related_name="metrics"
    )

    timestamp = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=50)
    value = models.FloatField()

    class Meta:
        indexes = [
            models.Index(fields=["agent", "timestamp"]),
            models.Index(fields=["name"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.agent.name} | {self.name} = {self.value}"


class GlobalConfig(models.Model):
    version = models.IntegerField(default=1)
    config = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)


class AgentConfig(models.Model):
    agent = models.OneToOneField(Agent, on_delete=models.CASCADE)
    override = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)


class UserDashboard(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dashboard')
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dashboard for {self.user.username}"


class NotificationTarget(models.Model):
    TARGET_TYPES = [
        ('telegram', 'Telegram Bot'),
        ('discord', 'Discord Bot'),
    ]

    name = models.CharField(max_length=100, verbose_name="Название")
    target_type = models.CharField(max_length=20, choices=TARGET_TYPES, verbose_name="Тип бота")
    token = models.CharField(max_length=255, verbose_name="Токен бота")
    channels = models.JSONField(default=list, verbose_name="ID каналов/чатов")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлен")

    class Meta:
        verbose_name = "Получатель уведомлений"
        verbose_name_plural = "Получатели уведомлений"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_target_type_display()}: {self.name}"

    def send_message(self, message):
        if self.target_type == 'telegram':
            return self._send_telegram(message)
        elif self.target_type == 'discord':
            return self._send_discord(message)
        return False

    def _send_telegram(self, message):
        if not self.token or not self.channels:
            print(f"[TELEGRAM] No token or channels configured for {self.name}")
            return False

        success_count = 0
        base_url = f"https://api.telegram.org/bot{self.token}"

        for chat_id in self.channels:
            try:
                response = requests.post(
                    f"{base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok'):
                        print(f"[TELEGRAM] Message sent to {chat_id}")
                        success_count += 1
                    else:
                        print(f"[TELEGRAM] API error for {chat_id}: {result.get('description')}")
                else:
                    print(f"[TELEGRAM] HTTP {response.status_code} for {chat_id}")

            except Exception as e:
                print(f"[TELEGRAM] Error sending to {chat_id}: {e}")

        return success_count > 0

    def _send_discord(self, message):
        if not self.channels:
            print(f"[DISCORD] No webhook URLs configured for {self.name}")
            return False

        success_count = 0

        for webhook_url in self.channels:
            try:
                if not webhook_url.startswith('http'):
                    webhook_url = f"https://discord.com/api/webhooks/{webhook_url}/{self.token}"

                response = requests.post(
                    webhook_url,
                    json={
                        "content": message,
                        "username": "PCMSI Monitoring"
                    },
                    timeout=10
                )

                if response.status_code == 204:
                    print(f"[DISCORD] Message sent successfully")
                    success_count += 1
                elif response.status_code == 200:
                    print(f"[DISCORD] Message sent (200 OK)")
                    success_count += 1
                else:
                    print(f"[DISCORD] HTTP {response.status_code}: {response.text}")

            except Exception as e:
                print(f"[DISCORD] Error sending webhook: {e}")

        return success_count > 0

    @classmethod
    def broadcast_to_all(cls, message):
        results = []
        for target in cls.objects.filter(is_active=True):
            try:
                success = target.send_message(message)
                results.append({
                    'target': target.name,
                    'success': success
                })
            except Exception as e:
                results.append({
                    'target': target.name,
                    'success': False,
                    'error': str(e)
                })
        return results


class AlertRule(models.Model):
    RULE_TYPES = [
        ('metric', 'Метрики агента'),
        ('host', 'Хосты сети'),
    ]
    name = models.CharField(max_length=200, verbose_name="Название правила")
    rule_type = models.CharField(max_length=10, choices=RULE_TYPES, default='metric')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Агент")
    host = models.ForeignKey('NetworkHost', on_delete=models.CASCADE, null=True, blank=True, verbose_name="Хост")
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    cooldown_minutes = models.IntegerField(default=5, verbose_name="Перерыв между алертами (мин)")
    last_triggered = models.DateTimeField(null=True, blank=True, verbose_name="Последний алерт")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Правило алерта"
        verbose_name_plural = "Правила алертов"
        ordering = ['-created_at']

    def __str__(self):
        if self.rule_type == 'metric' and self.agent:
            return f"{self.name} ({self.agent.name})"
        elif self.rule_type == 'host' and self.host:
            return f"{self.name} ({self.host.ip_address})"
        elif self.rule_type == 'host':
            return f"{self.name} (любой хост)"
        return self.name

    def check_conditions(self):
        conditions = self.conditions.filter(is_active=True)
        if not conditions.exists():
            return False

        for condition in conditions:
            if not condition.evaluate():
                return False

        return True

    def execute_actions(self):
        actions = self.actions.filter(is_active=True)
        results = []
        for action in actions:
            result = action.execute()
            results.append(result)
        return results

    def should_trigger(self):
        if not self.is_active:
            return False

        if self.last_triggered:
            from django.utils import timezone
            from datetime import timedelta
            if timezone.now() - self.last_triggered < timedelta(minutes=self.cooldown_minutes):
                return False

        return True


def compare_with_mask(value, mask_or_value, operator):
    if operator in ['in', 'not_in']:
        items = [x.strip() for x in mask_or_value.split(',') if x.strip()]
        matched = any(fnmatch.fnmatch(value, m) for m in items)
        return matched if operator == 'in' else not matched
    else:
        matched = fnmatch.fnmatch(value, mask_or_value)
        return matched if operator == '==' else not matched


class AlertCondition(models.Model):
    CONDITION_TYPES = [
        ('metric', 'Метрика'),
        ('host', 'Хост'),
    ]
    OPERATORS = [
        ('>', '> (больше)'),
        ('<', '< (меньше)'),
        ('>=', '>= (больше или равно)'),
        ('<=', '<= (меньше или равно)'),
        ('==', '== (равно)'),
        ('!=', '!= (не равно)'),
        ('in', 'среди'),
        ('not_in', 'не среди'),
    ]
    HOST_FIELDS = [
        ('port', 'Открытый порт'),
        ('online', 'Онлайн'),
        ('mac', 'MAC-адрес'),
        ('ip', 'IP-адрес'),
        ('trusted', 'Доверенный'),
    ]

    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='conditions')
    condition_type = models.CharField(max_length=10, choices=CONDITION_TYPES, default='metric')
    metric_name = models.CharField(max_length=100, null=True, blank=True)
    host_field = models.CharField(
        max_length=50, null=True, blank=True,
        choices=HOST_FIELDS,
        help_text="Поле хоста: port, online, mac, ip, trusted"
    )
    operator = models.CharField(max_length=20, choices=OPERATORS)
    threshold = models.FloatField(null=True, blank=True)
    value_str = models.CharField(max_length=255, null=True, blank=True,
                                 verbose_name="Значение (строка)")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Условие алерта"
        verbose_name_plural = "Условия алертов"

    def __str__(self):
        if self.condition_type == 'metric':
            return f"{self.metric_name} {self.operator} {self.threshold}"
        else:
            display = self.get_host_field_display() if self.host_field else '?'
            return f"{display} {self.operator} {self.value_str}"

    def evaluate(self):
        if self.condition_type != 'metric' or not self.metric_name:
            return False

        last_metric = Metric.objects.filter(
            agent=self.rule.agent,
            name=self.metric_name
        ).order_by('-timestamp').first()

        if not last_metric:
            return False

        value = last_metric.value

        if self.operator == '>':
            return value > self.threshold
        elif self.operator == '<':
            return value < self.threshold
        elif self.operator == '>=':
            return value >= self.threshold
        elif self.operator == '<=':
            return value <= self.threshold
        elif self.operator == '==':
            return value == self.threshold
        elif self.operator == '!=':
            return value != self.threshold
        return False

    def evaluate_host(self, host: 'NetworkHost') -> bool:
        if self.condition_type != 'host' or not self.host_field:
            return False

        field = self.host_field
        val = str(self.value_str) if self.value_str is not None else ""

        if field == 'port':
            if not host.ports_info or self.threshold is None:
                return False
            port_to_check = int(self.threshold)
            port_entry = host.ports_info.get(str(port_to_check))
            if self.operator in ['==', '!=']:
                state = port_entry.get('state', '') if port_entry else ''
                return (state == 'open') if self.operator == '==' else (state != 'open')
            elif self.operator == '>':
                return any(int(p) > port_to_check for p in host.ports_info.keys())
            elif self.operator == '<':
                return any(int(p) < port_to_check for p in host.ports_info.keys())
            elif self.operator == 'in':
                return str(port_to_check) in val.split(',')
            elif self.operator == 'not_in':
                return str(port_to_check) not in val.split(',')
            return False

        elif field == 'online':
            online = host.is_online
            desired = val.lower() in ('да', 'true', '1', 'yes')
            return (online == desired) if self.operator == '==' else (online != desired)

        elif field == 'mac':
            mac = host.mac_address or ''
            return compare_with_mask(mac, val, self.operator)

        elif field == 'ip':
            ip = host.ip_address
            return compare_with_mask(ip, val, self.operator)

        elif field == 'trusted':
            trusted = host.is_trusted
            desired = val.lower() in ('да', 'true', '1', 'yes')
            return (trusted == desired) if self.operator == '==' else (trusted != desired)

        return False


class AlertAction(models.Model):
    ACTION_TYPES = [
        ('telegram', 'Отправить в Telegram'),
        ('discord', 'Отправить в Discord'),
    ]

    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='actions', verbose_name="Правило")
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name="Тип действия")
    target = models.ForeignKey(NotificationTarget, on_delete=models.CASCADE, verbose_name="Бот-получатель")
    message = models.TextField(verbose_name="Сообщение")
    is_active = models.BooleanField(default=True, verbose_name="Активно")

    class Meta:
        verbose_name = "Действие алерта"
        verbose_name_plural = "Действия алертов"

    def __str__(self):
        return f"{self.get_action_type_display()} → {self.target.name}"

    def execute(self, host=None):
        if not self.target.is_active:
            return {'action': str(self), 'success': False, 'error': 'Бот отключен'}

        message_text = self.message

        if self.rule.rule_type == 'metric':
            conditions = self.rule.conditions.filter(is_active=True)
            for condition in conditions:
                if condition.condition_type == 'metric' and condition.metric_name:
                    last_metric = Metric.objects.filter(
                        agent=self.rule.agent,
                        name=condition.metric_name
                    ).order_by('-timestamp').first()
                    if last_metric:
                        message_text = message_text.replace(
                            f'{{{condition.metric_name}}}',
                            str(last_metric.value)
                        )
            message_text += f"\n\n📊 Правило: {self.rule.name}"
            if self.rule.agent:
                message_text += f"\n🖥 Агент: {self.rule.agent.name}"
        else:
            message_text += f"\n\n📡 Правило: {self.rule.name}"
            if host:
                message_text += f"\n🖥 Хост: {host.ip_address}"
                if host.hostname:
                    message_text += f" ({host.hostname})"
            else:
                message_text += "\nЦель: любой хост (алерт сработал)"

        message_text += f"\n⏰ {localtime(timezone.now()).strftime('%d.%m.%Y %H:%M:%S')}"

        success = self.target.send_message(message_text)
        return {
            'action': str(self),
            'success': success,
            'target': self.target.name
        }


class NetworkHost(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    hostname = models.CharField(max_length=255, blank=True, null=True)

    os_info = models.CharField(max_length=255, blank=True, null=True, verbose_name="ОС")
    manufacturer = models.CharField(max_length=255, blank=True, null=True, verbose_name="Производитель (MAC OUI)")
    DEVICE_TYPE_CHOICES = [
        ('unknown', 'Неизвестно'),
        ('router', 'Маршрутизатор'),
        ('switch', 'Коммутатор'),
        ('server', 'Сервер'),
        ('workstation', 'Рабочая станция'),
        ('printer', 'Принтер'),
        ('iot', 'IoT'),
        ('other', 'Другое'),
    ]
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES, default='unknown', verbose_name="Тип устройства")
    ports_info = models.JSONField(default=dict, blank=True, verbose_name="Порты (последнее сканирование)")
    notes = models.TextField(blank=True, verbose_name="Заметки")

    is_trusted = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    last_online = models.DateTimeField(null=True, blank=True)
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_online(self):
        if not self.last_online:
            return False
        from django.utils import timezone
        from datetime import timedelta
        return self.last_online >= timezone.now() - timedelta(minutes=5)

    class Meta:
        verbose_name = "Сетевой хост"
        verbose_name_plural = "Сетевые хосты"
        ordering = ['ip_address']

    def __str__(self):
        return f"{self.ip_address} ({self.hostname or 'N/A'})"


class NetworkScanSettings(models.Model):
    enabled = models.BooleanField(default=False, verbose_name="Автосканирование включено")
    interval_minutes = models.PositiveIntegerField(default=5, verbose_name="Интервал (минуты)")

    class Meta:
        verbose_name = "Настройки сканирования сети"
        verbose_name_plural = "Настройки сканирования сети"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Сканирование {'включено' if self.enabled else 'отключено'} (интервал: {self.interval_minutes} мин)"