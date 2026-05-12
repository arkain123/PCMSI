import subprocess, os, datetime, re, platform, ipaddress, socket, fcntl, struct
import xml.etree.ElementTree as ET
from django.utils import timezone
from django.conf import settings
from .models import NetworkHost, Agent
from .alert_checker import check_host_alerts

def get_server_ip():
    """IP-адрес основного интерфейса сервера"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_local_mac():
    """MAC-адрес интерфейса, через который сервер выходит в сеть"""
    server_ip = get_server_ip()
    # Перебираем все интерфейсы и ищем тот, чей IP совпадает с server_ip
    for iface_name in socket.if_nameindex():
        name = iface_name[1]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Получаем IP интерфейса
            ip_bytes = fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack('256s', name[:15].encode('utf-8'))
            )[20:24]
            iface_ip = socket.inet_ntoa(ip_bytes)
            if iface_ip == server_ip:
                # Получаем MAC этого интерфейса
                mac_bytes = fcntl.ioctl(
                    s.fileno(),
                    0x8927,  # SIOCGIFHWADDR
                    struct.pack('256s', name[:15].encode('utf-8'))
                )[18:24]
                return ':'.join('%02x' % b for b in mac_bytes).upper()
        except Exception:
            continue
        finally:
            s.close()
    return None

def get_local_network():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ipaddress.IPv4Network(f"{ip}/24", strict=False)

def run_nmap(args):
    try:
        result = subprocess.run(['nmap'] + args, capture_output=True, text=True, timeout=120)
        return result.stdout
    except Exception as e:
        print(f"nmap error: {e}")
        return ""

def parse_nmap_scan(network):
    xml_output = run_nmap(['-sn', '-oX', '-', str(network)])
    hosts = []
    try:
        root = ET.fromstring(xml_output)
        for host_elem in root.findall('host'):
            ip = None
            mac = None
            hostname = None
            for addr in host_elem.findall('address'):
                if addr.get('addrtype') == 'mac':
                    mac = addr.get('addr')
                elif addr.get('addrtype') == 'ipv4':
                    ip = addr.get('addr')
            hostnames = host_elem.find('hostnames')
            if hostnames is not None:
                hn_elem = hostnames.find('hostname')
                if hn_elem is not None:
                    hostname = hn_elem.get('name')
            if ip:
                hosts.append({'ip': ip, 'mac': mac, 'hostname': hostname})
    except Exception as e:
        print(f"XML parse error: {e}")
    return hosts

def get_mac_from_arp(ip):
    """Извлекает MAC для удалённого хоста из ARP-таблицы, для локального — через ioctl"""
    # Если это IP самого сервера — используем прямой метод
    if ip == get_server_ip():
        return get_local_mac()

    # Иначе пробуем ARP-таблицу
    try:
        system = platform.system().lower()
        if system == 'windows':
            output = subprocess.check_output(['arp', '-a', ip], timeout=2, universal_newlines=True)
            match = re.search(r'([0-9a-fA-F]{2}[-:]){5}([0-9a-fA-F]{2})', output)
            if match:
                return match.group(0).replace('-', ':').upper()
        else:  # Linux
            output = subprocess.check_output(['arp', '-n', ip], timeout=2, universal_newlines=True)
            for line in output.splitlines():
                if ip in line:
                    parts = line.split()
                    for part in parts:
                        if re.match(r'([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', part):
                            return part.upper()
    except Exception:
        pass
    return None

def perform_network_scan():
    log_path = os.path.join(settings.BASE_DIR, 'logs', 'scan_debug.log')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    with open(log_path, 'a') as log:
        now = timezone.now()
        log.write(f"\n=== {datetime.datetime.now()} ===\n")
        network = get_local_network()
        log.write(f"Local network: {network}\n")
        log.write("Running nmap...\n")

        xml_output = run_nmap(['-sn', '-oX', '-', str(network)])
        log.write(f"nmap XML output:\n{xml_output}\n")

        discovered = parse_nmap_scan(network)
        log.write(f"Discovered hosts: {discovered}\n")

        for item in discovered:
            ip = item['ip']
            host, created = NetworkHost.objects.get_or_create(ip_address=ip)
            host.last_seen = now
            host.last_online = now

            mac = item.get('mac')
            if not mac:
                mac = get_mac_from_arp(ip)
            host.mac_address = mac or host.mac_address

            host.hostname = item.get('hostname') or host.hostname

            if not host.manufacturer and host.mac_address:
                host.manufacturer = get_mac_vendor(host.mac_address[:8])

            host.agent = Agent.objects.filter(ip_address=ip, is_active=True).first()
            host.save()
            log.write(f"Updated host {ip}: mac={host.mac_address}, hostname={host.hostname}\n")

        log.write("Scan completed.\n")
    check_host_alerts()

def get_mac_vendor(mac_prefix):
    # В будущем можно реализовать запрос к API macvendors.com
    return ""

def scan_host_ports(host_ip, ports='1-1024'):
    xml = run_nmap(['-p', ports, '-oX', '-', host_ip])
    ports_data = {}
    try:
        root = ET.fromstring(xml)
        host_elem = root.find('host')
        if host_elem is not None:
            for port_elem in host_elem.findall('.//port'):
                port_id = port_elem.get('portid')
                service = port_elem.find('service')
                state = port_elem.find('state')
                if port_id and service is not None and state is not None:
                    ports_data[port_id] = {
                        'state': state.get('state'),
                        'service': service.get('name'),
                        'product': service.get('product'),
                        'version': service.get('version'),
                    }
    except Exception as e:
        print(f"Port parse error: {e}")
    return ports_data

def scan_host_os(host_ip):
    xml = run_nmap(['-O', '--osscan-guess', '-oX', '-', host_ip])
    os_info = ""
    try:
        root = ET.fromstring(xml)
        for osmatch in root.findall('.//osmatch'):
            os_info = osmatch.get('name')
            break
    except:
        pass
    return os_info