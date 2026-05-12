import threading
import time
from django.apps import AppConfig

class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoring'

    def ready(self):
        if threading.current_thread().name == "MainThread":
            from .network_utils import perform_network_scan
            from .models import NetworkScanSettings

            def scanner_worker():
                last_run = 0
                while True:
                    time.sleep(30)
                    try:
                        settings = NetworkScanSettings.load()
                        if settings.enabled:
                            interval_sec = settings.interval_minutes * 60
                            now = time.time()
                            if now - last_run >= interval_sec:
                                perform_network_scan()
                                last_run = now
                    except Exception:
                        pass

            t = threading.Thread(target=scanner_worker, daemon=True)
            t.start()