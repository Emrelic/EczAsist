"""
API Server Test - Ana makinede calistirin
Bu script API server'in duzgun calisip calismadigini test eder
"""

import sys
import socket
import requests
import time

def get_local_ip():
    """Yerel IP adresini al"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def test_port_open(host, port):
    """Port acik mi kontrol et"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def test_api_health(host, port):
    """API health endpoint'ini test et"""
    try:
        url = f"http://{host}:{port}/api/health"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return True, response.json()
        return False, f"HTTP {response.status_code}"
    except requests.exceptions.ConnectionError as e:
        return False, f"Baglanti hatasi: {e}"
    except requests.exceptions.Timeout:
        return False, "Zaman asimi"
    except Exception as e:
        return False, str(e)

def main():
    print("=" * 60)
    print("BOTANIK KASA - API SERVER TEST")
    print("=" * 60)

    local_ip = get_local_ip()
    port = 5000

    print(f"\n[INFO] Bu makinenin IP adresi: {local_ip}")
    print(f"[INFO] Test edilecek port: {port}")

    # 1. Localhost test
    print("\n" + "-" * 40)
    print("1) LOCALHOST TESTI (127.0.0.1)")
    print("-" * 40)

    if test_port_open("127.0.0.1", port):
        print(f"[OK] Port {port} acik")
        success, result = test_api_health("127.0.0.1", port)
        if success:
            print(f"[OK] API Server calisiyor!")
            print(f"    Detay: {result}")
        else:
            print(f"[HATA] API yanit vermiyor: {result}")
    else:
        print(f"[HATA] Port {port} KAPALI - API Server CALISMIYOR!")
        print("       API Server'i baslatin: python kasa_api_server.py")

    # 2. Network IP test
    print("\n" + "-" * 40)
    print(f"2) NETWORK TESTI ({local_ip})")
    print("-" * 40)

    if test_port_open(local_ip, port):
        print(f"[OK] Port {port} network uzerinden acik")
        success, result = test_api_health(local_ip, port)
        if success:
            print(f"[OK] API Server network uzerinden erisilebilir!")
        else:
            print(f"[HATA] API yanit vermiyor: {result}")
    else:
        print(f"[HATA] Port {port} network uzerinden KAPALI!")
        print("       Windows Firewall'u kontrol edin")

    # 3. API Server'i manuel baslat
    print("\n" + "-" * 40)
    print("3) COZUM ONERILERI")
    print("-" * 40)

    if not test_port_open("127.0.0.1", port):
        print("\nAPI Server calismiyor. Baslatmak icin:")
        print("   python kasa_api_server.py")

        cevap = input("\nAPI Server'i simdi baslatayim mi? (e/h): ")
        if cevap.lower() == 'e':
            print("\nAPI Server baslatiliyor...")
            import subprocess
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            server_path = os.path.join(script_dir, "kasa_api_server.py")
            subprocess.Popen(["python", server_path],
                           creationflags=subprocess.CREATE_NEW_CONSOLE)
            time.sleep(3)

            # Tekrar test et
            if test_port_open("127.0.0.1", port):
                print("[OK] API Server baslatildi!")
            else:
                print("[HATA] API Server baslatilamadi")
    else:
        print("\n[OK] API Server calisiyor")
        print(f"\nTerminal makinelerden baglanmak icin:")
        print(f"   Ana Makine IP: {local_ip}")
        print(f"   Port: {port}")

    print("\n" + "=" * 60)
    input("\nCikmak icin Enter'a basin...")

if __name__ == "__main__":
    main()
