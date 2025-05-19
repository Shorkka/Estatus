import psutil
import socket

def check_port(port):
    """Verifica si un puerto está en uso localmente."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def monitor_app(app_name, app_port):
    print(f"🔍 Monitoreando la aplicación: {app_name}")

    # Verifica el proceso
    is_running = any(
        p.info['name'] == app_name for p in psutil.process_iter(['name'])
    )
    print(f"  Proceso: {'🟢' if is_running else '🔴'} {app_name}")

    # Verifica el puerto
    is_port_open = check_port(app_port)
    print(f"  Puerto {app_port}: {'🟢' if is_port_open else '🔴'}")

    # Verifica recursos del sistema
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    print(f"\n📊 Recursos del sistema:")
    print(f"  CPU: {cpu}% | Memoria: {mem}% | Disco: {disk}%")

    # Alertas críticas
    if disk > 85:
        print("\n❌ ¡Urgente! Disco casi lleno (>85%).")

if __name__ == "__main__":
    monitor_app(app_name="python.exe", app_port=5000)
