from django.contrib import admin
from django.utils.timezone import localtime
from .models import Agent, Metric, GlobalConfig, AgentConfig


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "ip_address", "is_active", "last_seen")
    search_fields = ("name", "ip_address")
    list_filter = ("is_active",)


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = (
        "agent",
        "name",
        "value",
        "formatted_timestamp",
        "formatted_received",
    )

    list_filter = ("agent", "name")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"

    def formatted_timestamp(self, obj):
        return localtime(obj.timestamp).strftime("%d.%m.%Y %H:%M:%S")

    def formatted_received(self, obj):
        return localtime(obj.received_at).strftime("%d.%m.%Y %H:%M:%S")

    formatted_timestamp.short_description = "Timestamp"
    formatted_received.short_description = "Received at"


@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = ("version", "updated_at")
    readonly_fields = ("updated_at",)
    ordering = ("-version",)


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    list_display = ("agent", "updated_at")
    search_fields = ("agent__name",)
    ordering = ("-updated_at",)