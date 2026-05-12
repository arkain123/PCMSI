import subprocess
import ipaddress
import socket
from django.utils import timezone
from .models import NetworkHost, Agent
from .alert_checker import check_host_alerts

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
    import xml.etree.ElementTree as ET
    hosts = []
    try:
        root = ET.fromstring(xml_output)
        for host_elem in root.findall('host'):
            addr_elem = host_elem.find('address')
            ip = addr_elem.get('addr') if addr_elem is not None else None
            mac = hostname = None
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

def perform_network_scan():
    network = get_local_network()
    now = timezone.now()
    discovered = parse_nmap_scan(network)

    for item in discovered:
        ip = item['ip']
        host, created = NetworkHost.objects.get_or_create(ip_address=ip)
        host.last_seen = now
        host.last_online = now
        host.mac_address = item.get('mac') or host.mac_address
        host.hostname = item.get('hostname') or host.hostname

        if not host.manufacturer and host.mac_address:
            host.manufacturer = get_mac_vendor(host.mac_address[:8])

        host.agent = Agent.objects.filter(ip_address=ip, is_active=True).first()
        host.save()
    check_host_alerts()

def get_mac_vendor(mac_prefix):
    #api.macvendors.com
    return ""

def scan_host_ports(host_ip, ports='1-1024'):
    xml = run_nmap(['-p', ports, '-oX', '-', host_ip])
    ports_data = {}
    import xml.etree.ElementTree as ET
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
    import xml.etree.ElementTree as ET
    os_info = ""
    try:
        root = ET.fromstring(xml)
        for osmatch in root.findall('.//osmatch'):
            os_info = osmatch.get('name')
            break
    except:
        pass
    return os_info