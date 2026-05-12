from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('explore/', views.explore, name='explore'),
    path('datasources/', views.datasources, name='datasources'),
    path('metrics-config/', views.metrics_config, name='metrics_config'),
    path('api/metrics/', views.receive_metrics, name='receive_metrics'),
    path('api/chart/<uuid:agent_id>/<str:metric_name>/', views.chart_data, name='chart_data'),
    path('api/agent/<uuid:agent_id>/metrics/', views.agent_metrics_list, name='agent_metrics_list'),
    path('api/last/<uuid:agent_id>/<str:metric_name>/', views.last_value, name='last_value'),
    path('api/dashboard/load/', views.load_dashboard, name='load_dashboard'),
    path('api/dashboard/save/', views.save_dashboard, name='save_dashboard'),

    path('api/agent/create/', views.create_agent, name='create_agent'),
    path('api/agent/<uuid:agent_id>/update/', views.update_agent, name='update_agent'),
    path('api/agent/<uuid:agent_id>/toggle/', views.toggle_agent, name='toggle_agent'),
    path('api/agent/<uuid:agent_id>/delete/', views.delete_agent, name='delete_agent'),
    path('api/agent/<uuid:agent_id>/info/', views.agent_info, name='agent_info'),

    path('api/delete-agent-override/', views.delete_agent_override, name='delete_agent_override'),

    path('notification-targets/', views.notification_targets, name='notification_targets'),
    path('api/notification-target/create/', views.create_notification_target, name='create_notification_target'),
    path('api/notification-target/<int:target_id>/update/', views.update_notification_target, name='update_notification_target'),
    path('api/notification-target/<int:target_id>/toggle/', views.toggle_notification_target, name='toggle_notification_target'),
    path('api/notification-target/<int:target_id>/delete/', views.delete_notification_target, name='delete_notification_target'),
    path('api/notification-target/<int:target_id>/test/', views.test_notification_target, name='test_notification_target'),

    path('alert-rules/', views.alert_rules, name='alert_rules'),
    path('api/alert-rule/create/', views.create_alert_rule, name='create_alert_rule'),
    path('api/alert-rule/<int:rule_id>/update/', views.update_alert_rule, name='update_alert_rule'),
    path('api/alert-rule/<int:rule_id>/toggle/', views.toggle_alert_rule, name='toggle_alert_rule'),
    path('api/alert-rule/<int:rule_id>/delete/', views.delete_alert_rule, name='delete_alert_rule'),
    path('api/agent/<uuid:agent_id>/metrics-alerts/', views.get_agent_metrics_for_alerts, name='get_agent_metrics_for_alerts'),
    path('api/notification-targets/list/', views.get_notification_targets_for_alerts, name='get_notification_targets_for_alerts'),
    path('api/alert-rule/<int:rule_id>/', views.get_alert_rule, name='get_alert_rule'),

    path('network/', views.network_page, name='network'),
    path('api/network/scan/', views.trigger_network_scan, name='trigger_network_scan'),
    path('api/network/settings/', views.network_scan_settings, name='network_scan_settings'),
    path('api/network/hosts/clear/', views.clear_hosts, name='clear_hosts'),
    path('api/network/host/<int:host_id>/trust/', views.toggle_host_trust, name='toggle_host_trust'),
    path('api/network/host/<int:host_id>/update/', views.update_host_info, name='update_host_info'),
    path('api/network/host/<int:host_id>/delete/', views.delete_host, name='delete_host'),
    path('api/network/host/<int:host_id>/ports/', views.host_ports_api, name='host_ports_api'),
    path('api/network/host/<int:host_id>/os/', views.host_os_api, name='host_os_api'),
    path('api/hosts/list/', views.host_list_for_alerts, name='host_list_for_alerts'),
    path('api/alert-rule/host-fields/', views.host_condition_fields, name='host_condition_fields'),

    path('users/', views.user_management, name='user_management'),
    path('api/user/create/', views.create_user, name='create_user'),
    path('api/user/<int:user_id>/update/', views.update_user, name='update_user'),
    path('api/user/<int:user_id>/change-password/', views.change_user_password, name='change_user_password'),
    path('api/user/<int:user_id>/delete/', views.delete_user, name='delete_user'),
]