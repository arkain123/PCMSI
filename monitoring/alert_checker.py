from django.utils import timezone
from .models import AlertRule, NetworkHost


def check_host_alerts():
    """Проверяет все активные правила типа 'host' и выполняет действия"""
    rules = AlertRule.objects.filter(rule_type='host', is_active=True).prefetch_related('conditions', 'actions')

    for rule in rules:
        if not rule.should_trigger():
            continue

        hosts = NetworkHost.objects.all()
        if rule.host:
            hosts = hosts.filter(id=rule.host.id)

        for host in hosts:
            conditions = rule.conditions.filter(is_active=True)
            if all(condition.evaluate_host(host) for condition in conditions):
                for action in rule.actions.filter(is_active=True):
                    action.execute(host=host)

                rule.last_triggered = timezone.now()
                rule.save(update_fields=['last_triggered'])
                break
