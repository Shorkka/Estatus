import psutil
import os
import time
import socket
import requests
from datetime import datetime
import threading
import json
import platform
from collections import deque

class ServiceMonitor:
    def __init__(self, config_file='services_config.json'):
        self.services = self.load_config(config_file)
        self.history = {service['name']: deque(maxlen=100) for service in self.services}
        self.running = True
        self.status_symbols = {
            'up': '🟢',
            'down': '🔴',
            'warning': '🟡'
        }
        
    def load_config(self, config_file):
        """Carga la configuración desde un archivo JSON"""
        default_config = [
            {
                "name": "Web Service",
                "process_name": "python",
                "port": 5000,
                "endpoint": "http://localhost:5000/health",
                "required": True
            },
            {
                "name": "Database",
                "process_name": "postgres",
                "port": 5432,
                "required": True
            },
            {
                "name": "Cache",
                "process_name": "redis-server",
                "port": 6379,
                "required": False
            }
        ]
        
        try:
            with open(config_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Usando configuración por defecto (no se encontró {config_file})")
            return default_config
    
    def check_process(self, process_name):
        """Verifica si un proceso está en ejecución"""
        for proc in psutil.process_iter(['name', 'pid']):
            if process_name.lower() in proc.info['name'].lower():
                return True, proc.info['pid']
        return False, None
    
    def check_port(self, port):
        """Verifica si un puerto está en uso"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(('localhost', port)) == 0
    
    def check_endpoint(self, url):
        """Verifica un endpoint HTTP/HTTPS"""
        try:
            response = requests.get(url, timeout=3)
            return response.status_code == 200, response.status_code, response.elapsed.total_seconds()
        except requests.RequestException as e:
            return False, str(e), None
    
    def get_system_stats(self):
        """Obtiene estadísticas del sistema"""
        return {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'cpu': psutil.cpu_percent(),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent,
            'uptime': time.time() - psutil.boot_time()
        }
    
    def monitor_service(self, service):
        """Monitorea un servicio individual"""
        status = {'name': service['name'], 'required': service.get('required', False)}
        
        # Verificar proceso
        if 'process_name' in service:
            running, pid = self.check_process(service['process_name'])
            status['process'] = {
                'running': running,
                'pid': pid if running else None
            }
            if running:
                try:
                    proc = psutil.Process(pid)
                    with proc.oneshot():
                        status['process']['cpu'] = proc.cpu_percent()
                        status['process']['memory'] = proc.memory_info().rss / (1024 * 1024)  # MB
                        status['process']['threads'] = proc.num_threads()
                except psutil.NoSuchProcess:
                    status['process']['running'] = False
        
        # Verificar puerto
        if 'port' in service:
            port_open = self.check_port(service['port'])
            status['port'] = {
                'open': port_open,
                'number': service['port']
            }
        
        # Verificar endpoint
        if 'endpoint' in service:
            healthy, code, latency = self.check_endpoint(service['endpoint'])
            status['endpoint'] = {
                'healthy': healthy,
                'code': code,
                'latency': latency,
                'url': service['endpoint']
            }
        
        # Determinar estado general
        status['overall'] = self.determine_overall_status(status)
        return status
    
    def determine_overall_status(self, status):
        """Determina el estado general del servicio"""
        checks = []
        
        if 'process' in status:
            checks.append(status['process']['running'])
        
        if 'port' in status:
            checks.append(status['port']['open'])
        
        if 'endpoint' in status:
            checks.append(status['endpoint']['healthy'])
        
        if not checks:  # Si no hay checks definidos
            return 'unknown'
        
        if all(checks):
            return 'up'
        elif any(checks):
            return 'warning'
        else:
            return 'down'
    
    def display_status(self, system_stats, services_status):
        """Muestra el estado en la consola"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print(f"📊 Monitor de Servicios - {system_stats['timestamp']}")
        print(f"🏷️  Host: {socket.gethostname()} ({platform.system()} {platform.release()})")
        print(f"⏱️  Uptime: {int(system_stats['uptime'] // 3600)}h {int((system_stats['uptime'] % 3600) // 60)}m")
        print(f"🖥️  CPU: {system_stats['cpu']:.1f}% | 🧠 Memoria: {system_stats['memory']:.1f}% | 💾 Disco: {system_stats['disk']:.1f}%")
        print("\n🔍 Estado de los servicios:")
        
        for service in services_status:
            symbol = self.status_symbols.get(service['overall'], '⚪')
            req_tag = "(Requerido)" if service['required'] else "(Opcional)"
            print(f"\n{symbol} {service['name']} {req_tag}")
            
            if 'process' in service:
                status = service['process']
                if status['running']:
                    print(f"  • Proceso: {status['pid']} | CPU: {status.get('cpu', 0):.1f}% | Mem: {status.get('memory', 0):.2f}MB")
                else:
                    print("  • Proceso: No está corriendo")
            
            if 'port' in service:
                status = service['port']
                print(f"  • Puerto {status['number']}: {'Abierto ✅' if status['open'] else 'Cerrado ❌'}")
            
            if 'endpoint' in service:
                status = service['endpoint']
                if status['healthy']:
                    print(f"  • Endpoint: HTTP {status['code']} (Latencia: {status['latency']:.3f}s ✅")
                else:
                    print(f"  • Endpoint: Error ({status['code']}) ❌")
        
        print("\n🔄 Actualizando en 5 segundos (Ctrl+C para salir)...")
    
    def run(self):
        """Ejecuta el monitor principal"""
        try:
            while self.running:
                system_stats = self.get_system_stats()
                services_status = []
                
                for service in self.services:
                    status = self.monitor_service(service)
                    services_status.append(status)
                    self.history[service['name']].append(status)
                
                self.display_status(system_stats, services_status)
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n👋 Monitor detenido por el usuario")
    
    def save_report(self, filename='service_report.json'):
        """Guarda un reporte del estado actual"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'system': self.get_system_stats(),
            'services': [self.monitor_service(service) for service in self.services]
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📝 Reporte guardado en {filename}")

if __name__ == "__main__":
    monitor = ServiceMonitor()
    
    # Ejecutar en un hilo separado para permitir otras operaciones
    monitor_thread = threading.Thread(target=monitor.run, daemon=True)
    monitor_thread.start()
    
    # Ejemplo: Esperar 30 segundos y guardar un reporte
    time.sleep(30)
    monitor.save_report()
    
    # Detener después de 30 segundos (en un caso real, esto sería infinito)
    monitor.running = False
    monitor_thread.join()