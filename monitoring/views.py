import json, hmac, hashlib, traceback, uuid, threading, socket, re
from hmac import compare_digest
from datetime import datetime, timedelta
from time import timezone, time
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404, redirect
from .models import Agent, Metric, GlobalConfig, AgentConfig, UserDashboard, NotificationTarget, AlertRule, AlertAction, AlertCondition, NetworkHost, NetworkScanSettings
from .utils import deep_merge
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from .network_utils import perform_network_scan, scan_host_os, scan_host_ports

@csrf_exempt
def receive_metrics(request):
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Only POST allowed"}, status=405)

        agent_id = request.headers.get("X-Agent-ID")
        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")
        agent_config_version = request.headers.get("X-Config-Version", "0")

        agent = Agent.objects.get(id=agent_id, is_active=True)

        current_time = int(time())
        if abs(current_time - int(timestamp)) > 60:
            return JsonResponse({"error": "Expired request"}, status=403)

        message = request.body + timestamp.encode()
        expected_signature = hmac.new(
            agent.secret_key.encode(),
            message,
            hashlib.sha256
        ).hexdigest()

        if not compare_digest(expected_signature, signature):
            return JsonResponse({"error": "Invalid signature"}, status=403)

        payload = json.loads(request.body)
        metrics = payload.get("metrics", {})

        agent_timestamp = datetime.fromtimestamp(
            int(timestamp),
            tz=timezone.UTC
        )

        for name, value in metrics.items():
            Metric.objects.create(
                agent=agent,
                timestamp=agent_timestamp,
                name=name,
                value=float(value)
            )

        agent.last_seen = timezone.now()
        agent.save()

        global_config = GlobalConfig.objects.first()

        if global_config and global_config.config:
            final_config = global_config.config.copy()
        else:
            final_config = {}

        if global_config:
            final_version = str(global_config.version)
        else:
            final_version = "1"

        try:
            agent_override = AgentConfig.objects.get(agent=agent)
            if agent_override.override:
                final_config = deep_merge(final_config, agent_override.override)
                override_hash = hashlib.md5(
                    json.dumps(agent_override.override, sort_keys=True).encode()
                ).hexdigest()[:8]
                final_version = f"{final_version}_{override_hash}"
        except AgentConfig.DoesNotExist:
            pass

        final_config["config_version"] = final_version

        print(f"Agent {agent.name} (v{agent_config_version}) -> Server config (v{final_version})")

        response_data = {
            "status": "accepted",
            "config_version": final_version,
            "config": final_config
        }

        try:
            triggered = check_alerts()
            if triggered:
                print(f"Alerts triggered: {len(triggered)}")
                for trigger in triggered:
                    print(f"  - {trigger['rule']}")
        except Exception as e:
            print(f"Error checking alerts: {e}")

        return JsonResponse(response_data)

    except Agent.DoesNotExist:
        return JsonResponse({"error": "Agent not found"}, status=404)
    except Exception:
        print(traceback.format_exc())
        return JsonResponse({"error": "Server error"}, status=500)

@login_required
@csrf_exempt
def dashboard(request):
    agents = Agent.objects.filter(is_active=True)
    panels = []
    for agent in agents:
        unique_names = set(Metric.objects.filter(agent=agent).values_list('name', flat=True))
        for metric_name in sorted(unique_names):
            panels.append({'agent': agent, 'metric': metric_name})
    return render(request, 'monitoring/dashboard.html', {
        'agents': agents,
        'panels': panels,
        'available_metrics_json': json.dumps({str(a.id): list(set(Metric.objects.filter(agent=a).values_list('name', flat=True))) for a in agents}),
    })

@login_required
@csrf_exempt
def explore(request):
    agents = Agent.objects.filter(is_active=True)
    return render(request, 'monitoring/explore.html', {'agents': agents})

@login_required
@csrf_exempt
def datasources(request):
    agents = Agent.objects.all()
    return render(request, 'monitoring/datasources.html', {'agents': agents})

@login_required
@csrf_exempt
def metrics_config(request):
    agents = Agent.objects.filter(is_active=True)
    global_config = GlobalConfig.objects.first()
    agent_overrides = AgentConfig.objects.select_related('agent').all()
    overrides_dict = {}
    for ao in agent_overrides:
        overrides_dict[str(ao.agent.id)] = ao.override

    if request.method == 'POST':
        if 'global_config_json' in request.POST:
            try:
                config_data = json.loads(request.POST.get('global_config_json'))

                if global_config:
                    global_config.config = config_data
                    global_config.version += 1
                    global_config.save()
                else:
                    global_config = GlobalConfig.objects.create(
                        version=1,
                        config=config_data
                    )

                return JsonResponse({
                    'status': 'ok',
                    'version': global_config.version
                })
            except json.JSONDecodeError as e:
                return JsonResponse({'error': f'Невалидный JSON: {str(e)}'}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        elif 'agent_override_id' in request.POST:
            try:
                agent_id = request.POST.get('agent_override_id')
                override_json_str = request.POST.get('override_json')

                if not override_json_str:
                    return JsonResponse({'error': 'Конфигурация не может быть пустой'}, status=400)

                override_data = json.loads(override_json_str)

                if not isinstance(override_data, dict):
                    return JsonResponse({'error': 'Конфигурация должна быть JSON-объектом'}, status=400)

                agent = Agent.objects.get(id=agent_id)
                agent_conf, created = AgentConfig.objects.get_or_create(
                    agent=agent,
                    defaults={'override': override_data}
                )

                if not created:
                    agent_conf.override = override_data
                    agent_conf.save()

                return JsonResponse({
                    'status': 'ok',
                    'message': 'Конфигурация агента сохранена'
                })
            except Agent.DoesNotExist:
                return JsonResponse({'error': 'Агент не найден'}, status=404)
            except json.JSONDecodeError as e:
                return JsonResponse({'error': f'Невалидный JSON: {str(e)}'}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        return JsonResponse({'error': 'Invalid request'}, status=400)

    context = {
        'global_config': global_config,
        'agent_overrides': agent_overrides,
        'agents': agents,
        'agent_overrides_json': json.dumps(overrides_dict),
    }

    if global_config and global_config.config:
        context['global_config_json'] = json.dumps(global_config.config, indent=2, ensure_ascii=False)
    else:
        context['global_config_json'] = '{\n  "metrics": {},\n  "agent_runtime": {}\n}'

    return render(request, 'monitoring/metrics_config.html', context)

@login_required
@csrf_exempt
def delete_agent_override(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            agent_id = data.get('agent_id')

            agent_conf = AgentConfig.objects.get(agent_id=agent_id)
            agent_conf.delete()

            return JsonResponse({'status': 'ok', 'message': 'Конфигурация удалена'})
        except AgentConfig.DoesNotExist:
            return JsonResponse({'status': 'error', 'error': 'Конфигурация не найдена'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'error': 'Невалидный JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'error': 'Method not allowed'}, status=405)

def chart_data(request, agent_id, metric_name):
    hours = int(request.GET.get('hours', 2))
    agent = get_object_or_404(Agent, id=agent_id, is_active=True)
    since = timezone.now() - timedelta(hours=hours)
    metrics = Metric.objects.filter(
        agent=agent,
        name=metric_name,
        timestamp__gte=since
    ).order_by('timestamp')
    labels = [int(m.timestamp.timestamp() * 1000) for m in metrics]
    values = [m.value for m in metrics]
    return JsonResponse({
        'agent_name': agent.name,
        'metric': metric_name,
        'labels': labels,
        'values': values,
    })

def agent_metrics_list(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    metrics_names = list(Metric.objects.filter(agent=agent).values_list('name', flat=True).distinct())
    if not metrics_names:
        metrics_names = list(set(Metric.objects.filter(agent=agent).values_list('name', flat=True)))
    return JsonResponse(metrics_names, safe=False)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def create_agent(request):
    """Создание нового агента"""
    try:
        data = json.loads(request.body)

        agent = Agent(
            name=data.get('name'),
            ip_address=data.get('ip_address'),
            secret_key=data.get('secret_key') or uuid.uuid4().hex,
            is_active=True
        )
        agent.save()

        return JsonResponse({
            'status': 'ok',
            'agent_id': str(agent.id)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_agent(request, agent_id):
    """Обновление агента"""
    try:
        agent = get_object_or_404(Agent, id=agent_id)
        data = json.loads(request.body)

        agent.name = data.get('name', agent.name)
        agent.ip_address = data.get('ip_address', agent.ip_address)

        if data.get('secret_key'):
            agent.secret_key = data['secret_key']

        if 'is_active' in data:
            agent.is_active = data['is_active']

        agent.save()

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def toggle_agent(request, agent_id):
    """Включение/отключение агента"""
    try:
        agent = get_object_or_404(Agent, id=agent_id)
        data = json.loads(request.body)

        agent.is_active = data.get('is_active', not agent.is_active)
        agent.save()

        return JsonResponse({'status': 'ok', 'is_active': agent.is_active})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def delete_agent(request, agent_id):
    """Удаление агента и всех его метрик"""
    try:
        agent = get_object_or_404(Agent, id=agent_id)
        agent.delete()

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
def agent_info(request, agent_id):
    """Получение информации об агенте"""
    agent = get_object_or_404(Agent, id=agent_id)

    return JsonResponse({
        'id': str(agent.id),
        'name': agent.name,
        'ip_address': agent.ip_address,
        'secret_key': agent.secret_key,
        'is_active': agent.is_active,
        'last_seen': agent.last_seen.isoformat() if agent.last_seen else None,
        'created_at': agent.created_at.isoformat(),
        'metrics_count': Metric.objects.filter(agent=agent).count()
    })

def last_value(request, agent_id, metric_name):
    """Возвращает последнее значение метрики для gauge и stat"""
    try:
        last = Metric.objects.filter(agent_id=agent_id, name=metric_name).latest('timestamp')
        return JsonResponse({'value': last.value})
    except Metric.DoesNotExist:
        return JsonResponse({'value': None})

@login_required
@csrf_exempt
def load_dashboard(request):
    try:
        dashboard = UserDashboard.objects.get(user=request.user)
        return JsonResponse(dashboard.data)
    except UserDashboard.DoesNotExist:
        return JsonResponse({"version": 1, "panels": []})

@login_required
@csrf_exempt
def save_dashboard(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    dashboard, _ = UserDashboard.objects.get_or_create(user=request.user)

    dashboard.data = {
        "version": 1,
        "panels": data.get("panels", [])
    }

    dashboard.save()

    return JsonResponse({"status": "ok"})

@login_required
@csrf_exempt
def notification_targets(request):
    """Страница управления получателями уведомлений"""
    targets = NotificationTarget.objects.all()

    targets_json = []
    for t in targets:
        targets_json.append({
            'id': t.id,
            'name': t.name,
            'target_type': t.target_type,
            'token': t.token,
            'channels': t.channels,
            'is_active': t.is_active
        })

    return render(request, 'monitoring/notification_targets.html', {
        'targets': targets,
        'targets_json': json.dumps(targets_json)
    })

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def create_notification_target(request):
    """Создание нового получателя уведомлений"""
    try:
        data = json.loads(request.body)

        target = NotificationTarget.objects.create(
            name=data.get('name'),
            target_type=data.get('target_type'),
            token=data.get('token'),
            channels=data.get('channels', []),
            is_active=data.get('is_active', True)
        )

        return JsonResponse({
            'status': 'ok',
            'target_id': target.id,
            'message': 'Получатель создан'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_notification_target(request, target_id):
    """Обновление получателя уведомлений"""
    try:
        target = get_object_or_404(NotificationTarget, id=target_id)
        data = json.loads(request.body)

        target.name = data.get('name', target.name)
        target.target_type = data.get('target_type', target.target_type)

        if 'token' in data and data['token']:
            target.token = data['token']

        if 'channels' in data:
            target.channels = data['channels']

        if 'is_active' in data:
            target.is_active = data['is_active']

        target.save()

        return JsonResponse({
            'status': 'ok',
            'message': 'Получатель обновлен'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def toggle_notification_target(request, target_id):
    """Включение/отключение получателя"""
    try:
        target = get_object_or_404(NotificationTarget, id=target_id)
        data = json.loads(request.body)

        target.is_active = data.get('is_active', not target.is_active)
        target.save()

        return JsonResponse({
            'status': 'ok',
            'is_active': target.is_active
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def delete_notification_target(request, target_id):
    """Удаление получателя уведомлений"""
    try:
        target = get_object_or_404(NotificationTarget, id=target_id)
        target_name = target.name
        target.delete()

        return JsonResponse({
            'status': 'ok',
            'message': f'Получатель "{target_name}" удален'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
def test_notification_target(request, target_id):
    """Тестовая отправка сообщения"""
    try:
        target = get_object_or_404(NotificationTarget, id=target_id)

        test_message = f"🧪 Тестовое сообщение от PCMSI\n\nПолучатель: {target.name}\nТип: {target.get_target_type_display()}\nВремя: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"

        success = target.send_message(test_message)

        return JsonResponse({
            'status': 'ok',
            'success': success,
            'message': 'Тестовое сообщение отправлено' if success else 'Ошибка отправки'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
def alert_rules(request):
    """Страница управления правилами алертов"""
    rules = AlertRule.objects.all().prefetch_related('conditions', 'actions')
    agents = Agent.objects.filter(is_active=True)
    notification_targets = NotificationTarget.objects.filter(is_active=True)

    return render(request, 'monitoring/alert_rules.html', {
        'rules': rules,
        'agents': agents,
        'notification_targets': notification_targets,
    })

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def create_alert_rule(request):
    """Создание правила алерта (метрика или хост)"""
    try:
        data = json.loads(request.body)
        rule_type = data.get('rule_type', 'metric')

        rule = AlertRule.objects.create(
            name=data.get('name'),
            rule_type=rule_type,
            cooldown_minutes=data.get('cooldown_minutes', 5),
            is_active=data.get('is_active', True)
        )

        if rule_type == 'metric':
            agent_id = data.get('agent_id')
            if not agent_id:
                raise ValueError('agent_id обязателен для метрического правила')
            rule.agent = Agent.objects.get(id=agent_id)
        else:
            host_id = data.get('host_id')
            if host_id:
                rule.host = NetworkHost.objects.get(id=host_id)

        rule.save()

        for cond_data in data.get('conditions', []):
            if rule_type == 'metric':
                AlertCondition.objects.create(
                    rule=rule,
                    condition_type='metric',
                    metric_name=cond_data['metric_name'],
                    operator=cond_data['operator'],
                    threshold=float(cond_data['threshold']),
                    is_active=cond_data.get('is_active', True)
                )
            else:
                host_field = cond_data['host_field']
                operator = cond_data['operator']
                value_str = cond_data.get('value_str', '')
                threshold = cond_data.get('threshold')
                AlertCondition.objects.create(
                    rule=rule,
                    condition_type='host',
                    host_field=host_field,
                    operator=operator,
                    value_str=str(value_str),
                    threshold=float(threshold) if threshold is not None else None,
                    is_active=cond_data.get('is_active', True)
                )

        for action_data in data.get('actions', []):
            target = NotificationTarget.objects.get(id=action_data['target_id'])
            AlertAction.objects.create(
                rule=rule,
                action_type=action_data['action_type'],
                target=target,
                message=action_data['message'],
                is_active=action_data.get('is_active', True)
            )

        return JsonResponse({
            'status': 'ok',
            'rule_id': rule.id,
            'message': 'Правило создано'
        })
    except Agent.DoesNotExist:
        return JsonResponse({'error': 'Агент не найден'}, status=400)
    except NetworkHost.DoesNotExist:
        return JsonResponse({'error': 'Хост не найден'}, status=400)
    except NotificationTarget.DoesNotExist:
        return JsonResponse({'error': 'Получатель уведомлений не найден'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_alert_rule(request, rule_id):
    """Обновление правила алерта"""
    try:
        rule = get_object_or_404(AlertRule, id=rule_id)
        data = json.loads(request.body)

        rule.name = data.get('name', rule.name)
        rule.cooldown_minutes = data.get('cooldown_minutes', rule.cooldown_minutes)
        if 'is_active' in data:
            rule.is_active = data['is_active']

        if rule.rule_type == 'metric':
            if 'agent_id' in data:
                rule.agent = Agent.objects.get(id=data['agent_id'])
        else:
            if 'host_id' in data:
                host_id = data['host_id']
                if host_id:
                    rule.host = NetworkHost.objects.get(id=host_id)
                else:
                    rule.host = None

        rule.save()

        if 'conditions' in data:
            rule.conditions.all().delete()
            for cond_data in data['conditions']:
                if rule.rule_type == 'metric':
                    AlertCondition.objects.create(
                        rule=rule,
                        condition_type='metric',
                        metric_name=cond_data['metric_name'],
                        operator=cond_data['operator'],
                        threshold=float(cond_data['threshold']),
                        is_active=cond_data.get('is_active', True)
                    )
                else:
                    host_field = cond_data['host_field']
                    operator = cond_data['operator']
                    value_str = cond_data.get('value_str', '')
                    threshold = cond_data.get('threshold')
                    AlertCondition.objects.create(
                        rule=rule,
                        condition_type='host',
                        host_field=host_field,
                        operator=operator,
                        value_str=str(value_str),
                        threshold=float(threshold) if threshold is not None else None,
                        is_active=cond_data.get('is_active', True)
                    )

        if 'actions' in data:
            rule.actions.all().delete()
            for action_data in data['actions']:
                target = NotificationTarget.objects.get(id=action_data['target_id'])
                AlertAction.objects.create(
                    rule=rule,
                    action_type=action_data['action_type'],
                    target=target,
                    message=action_data['message'],
                    is_active=action_data.get('is_active', True)
                )

        return JsonResponse({'status': 'ok', 'message': 'Правило обновлено'})
    except Agent.DoesNotExist:
        return JsonResponse({'error': 'Агент не найден'}, status=400)
    except NetworkHost.DoesNotExist:
        return JsonResponse({'error': 'Хост не найден'}, status=400)
    except NotificationTarget.DoesNotExist:
        return JsonResponse({'error': 'Получатель уведомлений не найден'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def toggle_alert_rule(request, rule_id):
    """Включение/отключение правила"""
    try:
        rule = get_object_or_404(AlertRule, id=rule_id)
        data = json.loads(request.body)

        rule.is_active = data.get('is_active', not rule.is_active)
        rule.save()

        return JsonResponse({'status': 'ok', 'is_active': rule.is_active})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def delete_alert_rule(request, rule_id):
    """Удаление правила алерта"""
    try:
        rule = get_object_or_404(AlertRule, id=rule_id)
        rule.delete()

        return JsonResponse({'status': 'ok', 'message': 'Правило удалено'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def get_agent_metrics_for_alerts(request, agent_id):
    """Получение уникальных метрик агента для алертов"""
    agent = get_object_or_404(Agent, id=agent_id)
    metrics_names = list(set(Metric.objects.filter(agent=agent).values_list('name', flat=True)))
    metrics_names.sort()
    return JsonResponse(metrics_names, safe=False)

@login_required
@csrf_exempt
def get_alert_rule(request, rule_id):
    """Получение данных правила для редактирования (поддерживает метрики и хосты)"""
    rule = get_object_or_404(AlertRule, id=rule_id)

    conditions_data = []
    for cond in rule.conditions.all():
        c = {
            'id': cond.id,
            'condition_type': cond.condition_type,
            'operator': cond.operator,
            'is_active': cond.is_active,
        }
        if cond.condition_type == 'metric':
            c['metric_name'] = cond.metric_name
            c['threshold'] = cond.threshold
        else:
            c['host_field'] = cond.host_field
            c['value_str'] = cond.value_str
            c['threshold'] = cond.threshold
        conditions_data.append(c)

    actions_data = []
    for action in rule.actions.all():
        actions_data.append({
            'id': action.id,
            'action_type': action.action_type,
            'target_id': action.target.id,
            'target_name': action.target.name,
            'message': action.message,
            'is_active': action.is_active,
        })

    response = {
        'id': rule.id,
        'name': rule.name,
        'rule_type': rule.rule_type,
        'cooldown_minutes': rule.cooldown_minutes,
        'is_active': rule.is_active,
        'conditions': conditions_data,
        'actions': actions_data,
    }

    if rule.rule_type == 'metric' and rule.agent:
        response['agent_id'] = str(rule.agent.id)
        response['agent_name'] = rule.agent.name
    elif rule.rule_type == 'host':
        response['host_id'] = str(rule.host_id) if rule.host_id else None
        response['host_name'] = f"{rule.host.ip_address} ({rule.host.hostname})" if rule.host else 'Любой хост'

    return JsonResponse(response)

def get_notification_targets_for_alerts(request):
    """Получение списка ботов для действий"""
    targets = NotificationTarget.objects.filter(is_active=True).values('id', 'name', 'target_type')
    return JsonResponse(list(targets), safe=False)

def check_alerts():
    """Проверка всех алертов (вызывается при получении метрик)"""
    rules = AlertRule.objects.filter(is_active=True).prefetch_related('conditions', 'actions')

    triggered_rules = []

    for rule in rules:
        if not rule.should_trigger():
            continue

        if rule.check_conditions():
            results = rule.execute_actions()
            rule.last_triggered = timezone.now()
            rule.save()

            triggered_rules.append({
                'rule': rule.name,
                'results': results
            })

    return triggered_rules

@csrf_exempt
def login_view(request):
    """Кастомная страница логина"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                next_url = request.POST.get('next', '')
                if next_url:
                    return redirect(next_url)
                return redirect('dashboard')
    else:
        form = AuthenticationForm()

    return render(request, 'monitoring/login.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })

@csrf_exempt
def logout_view(request):
    """Выход из системы"""
    logout(request)
    return redirect('login')

@login_required
def network_page(request):
    hosts = NetworkHost.objects.all()
    scan_settings = None
    if request.user.is_superuser:
        scan_settings = NetworkScanSettings.load()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        server_ip = s.getsockname()[0]
        s.close()
    except Exception:
        server_ip = '127.0.0.1'

    master_host = NetworkHost.objects.filter(ip_address=server_ip).first()
    master_host_id = master_host.id if master_host else None

    return render(request, 'monitoring/network.html', {
        'hosts': hosts,
        'scan_settings': scan_settings,
        'is_superuser': request.user.is_superuser,
        'server_ip': server_ip,
        'master_host_id': master_host_id,
    })

@login_required
def trigger_network_scan(request):
    if request.method == 'POST':
        thread = threading.Thread(target=perform_network_scan)
        thread.start()
        return JsonResponse({'status': 'scan_started'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def toggle_host_trust(request, host_id):
    host = get_object_or_404(NetworkHost, id=host_id)
    host.is_trusted = not host.is_trusted
    host.save()
    return JsonResponse({'status': 'ok', 'is_trusted': host.is_trusted})

@login_required
@require_http_methods(["GET", "POST"])
def network_scan_settings(request):
    """Получение и обновление настроек сканирования (только суперпользователь)"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    settings = NetworkScanSettings.load()

    if request.method == 'GET':
        return JsonResponse({
            'enabled': settings.enabled,
            'interval_minutes': settings.interval_minutes,
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        settings.enabled = data.get('enabled', settings.enabled)
        settings.interval_minutes = int(data.get('interval_minutes', settings.interval_minutes))
        settings.save()
        return JsonResponse({
            'status': 'ok',
            'enabled': settings.enabled,
            'interval_minutes': settings.interval_minutes,
        })

    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
@require_http_methods(["POST"])
def update_host_info(request, host_id):
    """Ручное обновление информации о хосте"""
    host = get_object_or_404(NetworkHost, id=host_id)
    data = json.loads(request.body)
    host.hostname = data.get('hostname', host.hostname)
    host.device_type = data.get('device_type', host.device_type)
    host.os_info = data.get('os_info', host.os_info)
    host.manufacturer = data.get('manufacturer', host.manufacturer)
    host.notes = data.get('notes', host.notes)
    host.save()
    return JsonResponse({'status': 'ok'})

@login_required
@require_http_methods(["DELETE"])
def delete_host(request, host_id):
    host = get_object_or_404(NetworkHost, id=host_id)
    host.delete()
    return JsonResponse({'status': 'ok'})

@login_required
def host_ports_api(request, host_id):
    """Получить последнее сканирование портов или запустить новое"""
    host = get_object_or_404(NetworkHost, id=host_id)
    if request.method == 'GET':
        return JsonResponse(host.ports_info)
    elif request.method == 'POST':
        ports_data = scan_host_ports(str(host.ip_address))
        host.ports_info = ports_data
        host.save()
        return JsonResponse({'status': 'ok', 'ports': ports_data})

@login_required
def host_os_api(request, host_id):
    """Запустить определение ОС для хоста"""
    host = get_object_or_404(NetworkHost, id=host_id)
    os_info = scan_host_os(str(host.ip_address))
    if os_info:
        host.os_info = os_info
        host.save()
    return JsonResponse({'os_info': os_info})

@login_required
@require_http_methods(["DELETE"])
def clear_hosts(request):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        server_ip = s.getsockname()[0]
        s.close()
    except Exception:
        server_ip = '127.0.0.1'
    count, _ = NetworkHost.objects.exclude(ip_address=server_ip).delete()
    return JsonResponse({'status': 'ok', 'deleted': count})

def host_list_for_alerts(request):
    hosts = NetworkHost.objects.all().values('id', 'ip_address', 'hostname')
    result = []
    for h in hosts:
        result.append({
            'id': h['id'],
            'name': f"{h['ip_address']} ({h['hostname'] or 'N/A'})",
        })
    return JsonResponse(result, safe=False)

def host_condition_fields(request):
    """Возвращает доступные поля хоста и их операторы для условий"""
    fields = {
        'port': {
            'label': 'Открытый порт',
            'operators': ['==', '!=', '>', '<', 'in', 'not_in'],
            'value_type': 'number',
        },
        'online': {
            'label': 'Онлайн',
            'operators': ['==', '!='],
            'value_type': 'boolean',
        },
        'mac': {
            'label': 'MAC',
            'operators': ['==', '!=', 'in', 'not_in'],
            'value_type': 'string',
        },
        'ip': {
            'label': 'IP-адрес',
            'operators': ['==', '!=', 'in', 'not_in'],
            'value_type': 'string',
            'help': 'Поддерживаются маски (192.168.*.*)',
        },
        'trusted': {
            'label': 'Доверенный',
            'operators': ['==', '!='],
            'value_type': 'boolean',
        },
    }
    return JsonResponse(fields)

@login_required
def user_management(request):
    """Страница управления пользователями (только для суперпользователя)"""
    if not request.user.is_superuser:
        return HttpResponse('Доступ запрещён', status=403)
    users = User.objects.all().order_by('username')
    return render(request, 'monitoring/user_management.html', {
        'users': users,
        'current_user_id': request.user.id,
    })


@login_required
@require_http_methods(["POST"])
def create_user(request):
    """Создание нового пользователя (только суперпользователь)"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Невалидный JSON'}, status=400)

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    is_superuser = data.get('is_superuser', False)
    is_active = data.get('is_active', True)

    if not username or not password:
        return JsonResponse({'error': 'Имя пользователя и пароль обязательны'}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({'error': 'Пользователь с таким именем уже существует'}, status=400)
    if email and User.objects.filter(email__iexact=email).exists():
        return JsonResponse({'error': 'Пользователь с таким email уже существует'}, status=400)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
    )
    user.is_superuser = is_superuser
    user.is_active = is_active
    user.save()
    return JsonResponse({'status': 'ok', 'user_id': user.id})


@login_required
@require_http_methods(["POST"])
def update_user(request, user_id):
    """Обновление данных пользователя (только суперпользователь)"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Невалидный JSON'}, status=400)

    user = get_object_or_404(User, id=user_id)
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    is_superuser = data.get('is_superuser', user.is_superuser)
    is_active = data.get('is_active', user.is_active)

    if not username:
        return JsonResponse({'error': 'Имя пользователя обязательно'}, status=400)
    if User.objects.filter(username=username).exclude(id=user_id).exists():
        return JsonResponse({'error': 'Пользователь с таким именем уже существует'}, status=400)
    if email and User.objects.filter(email__iexact=email).exclude(id=user_id).exists():
        return JsonResponse({'error': 'Пользователь с таким email уже существует'}, status=400)

    user.username = username
    user.email = email
    user.is_superuser = is_superuser
    user.is_active = is_active
    user.save()
    return JsonResponse({'status': 'ok'})


@login_required
@require_http_methods(["POST"])
def change_user_password(request, user_id):
    """Смена пароля пользователя (только суперпользователь)"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Невалидный JSON'}, status=400)

    user = get_object_or_404(User, id=user_id)
    new_password = data.get('password', '').strip()
    if not new_password:
        return JsonResponse({'error': 'Пароль не может быть пустым'}, status=400)
    user.set_password(new_password)
    user.save()
    return JsonResponse({'status': 'ok'})


@login_required
@require_http_methods(["DELETE"])
def delete_user(request, user_id):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)

    user = get_object_or_404(User, id=user_id)
    if user.id == request.user.id:
        return JsonResponse({'error': 'Нельзя удалить самого себя'}, status=400)

    UserDashboard.objects.filter(user=user).delete()
    user.delete()
    return JsonResponse({'status': 'ok'})