from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .models import Metric


def metrics(request, agent_id):

    metric = request.GET.get("metric")

    since = timezone.now() - timedelta(hours=2)

    qs = Metric.objects.filter(
        agent_id=agent_id,
        name=metric,
        timestamp__gte=since
    ).order_by("timestamp")

    return JsonResponse({
        "labels":[m.timestamp.strftime("%H:%M:%S") for m in qs],
        "values":[m.value for m in qs]
    })

