import requests
import hmac
import hashlib
import time
import json
import psutil
import socket
import platform
import logging
import yaml

# ================= CONFIG =================

CONFIG_FILE = "config.yaml"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(cfg, f, sort_keys=False)

config = load_config()

AGENT_ID = config["agent"]["id"]
SECRET_KEY = config["agent"]["api_key"]
MASTER_URL = config["master"]["url"]
TIMEOUT = config["master"]["timeout"]

CONFIG_VERSION = config.get("config_version", 1)

# ================= LOGGING =================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ================= STATIC INFO =================

STATIC_INFO = {
    "hostname": socket.gethostname(),
    "ip": socket.gethostbyname(socket.gethostname()),
    "os": platform.system(),
    "os_version": platform.release(),
    "cores": psutil.cpu_count(logical=True)
}

# ================= CONFIG APPLY =================

def apply_config(new_config):
    global config, CONFIG_VERSION

    logging.info("========== APPLYING NEW CONFIG ==========")

    new_version = new_config.get("config_version", CONFIG_VERSION)

    if str(new_version) == str(CONFIG_VERSION):
        logging.info(f"Version unchanged ({CONFIG_VERSION}) - skipping update")
        return

    logging.info(f"Updating from version {CONFIG_VERSION} to {new_version}")

    if "metrics" in new_config:
        old_metrics = config.get("metrics", {})
        config["metrics"] = new_config["metrics"]
        logging.info(f"Metrics updated: {old_metrics} -> {config['metrics']}")

    if "agent_runtime" in new_config:
        old_runtime = config.get("agent_runtime", {})
        config["agent_runtime"] = new_config["agent_runtime"]
        logging.info(f"Runtime updated: {old_runtime} -> {config['agent_runtime']}")

    CONFIG_VERSION = new_version
    config["config_version"] = CONFIG_VERSION

    logging.info(f"New config applied successfully")
    logging.info("==========================================")

    save_config(config)

# ================= METRICS =================

def collect_metrics():
    metrics = {}
    enabled = config.get("metrics", {})

    if enabled.get("cpu"):
        metrics["cpu_percent"] = psutil.cpu_percent()

    if enabled.get("ram"):
        mem = psutil.virtual_memory()
        metrics["ram_percent"] = mem.percent
        metrics["ram_used"] = mem.used
        metrics["ram_total"] = mem.total

    if enabled.get("disk"):
        disk = psutil.disk_usage("/")
        metrics["disk_percent"] = disk.percent
        metrics["disk_used"] = disk.used
        metrics["disk_total"] = disk.total

    if enabled.get("network"):
        net = psutil.net_io_counters()
        metrics["net_bytes_sent"] = net.bytes_sent
        metrics["net_bytes_recv"] = net.bytes_recv

    if enabled.get("system"):
        uptime = int(time.time() - psutil.boot_time())
        metrics["uptime_seconds"] = uptime

    if enabled.get("load_avg") and hasattr(psutil, "getloadavg"):
        load = psutil.getloadavg()
        metrics["load_1min"] = load[0]
        metrics["load_5min"] = load[1]
        metrics["load_15min"] = load[2]

    logging.info(f"Sending metrics: {list(metrics.keys())}")

    return {
        "metrics": metrics,
        "timestamp": int(time.time())
    }

# ================= SEND =================

def send_metrics(payload):
    global CONFIG_VERSION

    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))

    signature = hmac.new(
        SECRET_KEY.encode(),
        body + timestamp.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Agent-ID": AGENT_ID,
        "X-Timestamp": timestamp,
        "X-Signature": signature,
        "X-Config-Version": str(CONFIG_VERSION)
    }

    try:
        response = requests.post(
            MASTER_URL,
            data=body,
            headers=headers,
            timeout=TIMEOUT
        )

        logging.info(f"Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logging.info(f"Response data: {data}")

            if "config" in data:
                new_version = data.get("config_version", CONFIG_VERSION)
                logging.info(f"Current version: {CONFIG_VERSION}, New version: {new_version}")
                logging.info(f"Versions equal: {str(new_version) == str(CONFIG_VERSION)}")

                if str(new_version) != str(CONFIG_VERSION):
                    logging.info("VERSION CHANGED - applying new config")
                    data["config"]["config_version"] = new_version
                    apply_config(data["config"])
                else:
                    logging.info("Version unchanged - skipping config update")
            else:
                logging.info("No config in response")

        else:
            logging.warning(f"Bad response: {response.status_code}")
            logging.warning(f"Response text: {response.text}")

    except Exception as e:
        logging.error(f"Send failed: {e}")

# ================= MAIN LOOP =================

def main():
    logging.info("Agent started")
    logging.info(f"Initial config version: {CONFIG_VERSION}")
    logging.info(f"Initial metrics config: {config.get('metrics')}")

    while True:
        payload = collect_metrics()
        send_metrics(payload)

        interval = config.get("agent_runtime", {}).get("interval_seconds", 10)
        time.sleep(interval)

if __name__ == "__main__":
    main()