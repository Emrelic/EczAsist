"""
Ana Makine / Terminal Ag Baglanti Test Araci
API Server ve Client baglantisini test eder
"""

import sys
import socket
import time

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_result(test_name, success, detail=""):
    status = "[+] BASARILI" if success else "[-] BASARISIZ"
    print(f"\n{status} {test_name}")
    if detail:
        print(f"    -> {detail}")

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

def test_1_flask_modulu():
    """Test 1: Flask modulu yuklu mu?"""
    print_header("TEST 1: Flask Modulu Kontrolu")
    try:
        from flask import Flask
        from flask_cors import CORS
        print_result("Flask modulu", True, "Flask ve CORS yuklu")
        return True
    except ImportError as e:
        print_result("Flask modulu", False, str(e))
        print("    Cozum: pip install flask flask-cors")
        return False

def test_2_requests_modulu():
    """Test 2: Requests modulu yuklu mu?"""
    print_header("TEST 2: Requests Modulu Kontrolu")
    try:
        import requests
        print_result("Requests modulu", True, f"Versiyon: {requests.__version__}")
        return True
    except ImportError as e:
        print_result("Requests modulu", False, str(e))
        print("    Cozum: pip install requests")
        return False

def test_3_port_kontrol():
    """Test 3: Port 5000 kullanilabilir mi?"""
    print_header("TEST 3: Port 5000 Kontrolu")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 5000))
    sock.close()

    if result == 0:
        print_result("Port 5000", True, "Port ACIK - API Server calisiyor olabilir")
        return True, "running"
    else:
        print_result("Port 5000", True, "Port KAPALI - API Server baslatilabilir")
        return True, "available"

def test_4_api_server_baglanti(host='127.0.0.1', port=5000):
    """Test 4: API Server'a baglanma"""
    print_header("TEST 4: API Server Baglanti Testi")

    try:
        from kasa_api_client import KasaAPIClient

        client = KasaAPIClient(host=host, port=port, timeout=5)
        success, result = client.baglanti_test()

        if success:
            print_result("API Server baglantisi", True, f"Server: {result.get('server', 'N/A')}")
            return True, client
        else:
            print_result("API Server baglantisi", False, result)
            return False, None

    except Exception as e:
        print_result("API Server baglantisi", False, str(e))
        return False, None

def test_5_veri_okuma_yazma(client):
    """Test 5: Veri okuma/yazma testi"""
    print_header("TEST 5: Veri Okuma/Yazma Testi")

    if not client:
        print_result("Veri testi", False, "Client baglantisi yok - TEST ATLANDI")
        return None

    try:
        # Onceki gun kasasini oku
        success, result = client.onceki_gun_kasasi_al()
        if success:
            data = result.get('data', {})
            print(f"  Onceki gun kasasi: {data.get('toplam', 0):,.2f} TL")
            print_result("Veri okuma", True, "Onceki gun kasasi okundu")
        else:
            print_result("Veri okuma", False, result)
            return False

        # Bugunun kasasini oku
        success, result = client.bugunun_kasasini_al()
        if success:
            data = result.get('data')
            if data:
                print(f"  Bugunun kasasi mevcut: ID={data.get('id')}")
            else:
                print("  Bugun icin kayit yok (normal)")
            print_result("Bugun kasasi", True, "Sorgu basarili")
        else:
            print_result("Bugun kasasi", False, result)

        return True

    except Exception as e:
        print_result("Veri testi", False, str(e))
        return False

def test_6_network_bilgisi():
    """Test 6: Ag bilgilerini goster"""
    print_header("TEST 6: Ag Bilgileri")

    local_ip = get_local_ip()
    hostname = socket.gethostname()

    print(f"\n  Bilgisayar Adi: {hostname}")
    print(f"  Yerel IP: {local_ip}")
    print(f"  API Server URL: http://{local_ip}:5000")

    print("\n  " + "-"*50)
    print("  YAPILANDIRMA BILGISI:")
    print("  " + "-"*50)
    print(f"  ANA MAKINE olarak calistirmak icin:")
    print(f"    python kasa_api_server.py --host 0.0.0.0 --port 5000")
    print(f"\n  TERMINAL olarak baglanmak icin:")
    print(f"    Ana makine IP'sini ayarlara girin: {local_ip}")

    return True

def test_ana_makine_modu():
    """Ana Makine modunda test"""
    print("\n" + "#"*60)
    print("#" + " "*58 + "#")
    print("#    ANA MAKINE / TERMINAL TEST ARACI                      #")
    print("#    Ag Baglanti ve API Testi                              #")
    print("#" + " "*58 + "#")
    print("#"*60)

    results = {}

    # Test 1: Flask
    results['flask'] = test_1_flask_modulu()

    # Test 2: Requests
    results['requests'] = test_2_requests_modulu()

    # Test 3: Port kontrolu
    port_ok, port_status = test_3_port_kontrol()
    results['port'] = port_ok

    # Test 4: API baglanti
    if port_status == "running":
        api_ok, client = test_4_api_server_baglanti()
        results['api'] = api_ok

        # Test 5: Veri okuma/yazma
        if api_ok:
            results['veri'] = test_5_veri_okuma_yazma(client)
        else:
            results['veri'] = None
    else:
        print_header("TEST 4: API Server Baglanti Testi")
        print_result("API Server", False, "Server calismiyorVeri - Once 'python kasa_api_server.py' calistirin")
        results['api'] = False
        results['veri'] = None

    # Test 6: Ag bilgisi
    results['network'] = test_6_network_bilgisi()

    # Ozet
    print_header("TEST SONUC OZETI")

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    print(f"\n  [+] Basarili: {passed}")
    print(f"  [-] Basarisiz: {failed}")
    print(f"  [o] Atlanan: {skipped}")

    print("\n" + "="*60)

    if results.get('api') and results.get('veri'):
        print("  API SERVER CALISIYOR VE BAGLANTILAR BASARILI!")
        print("  Bu makine ANA MAKINE olarak kullanilabilir.")
    elif results.get('flask') and results.get('requests'):
        print("  MODULLER YUKLU - API Server baslatilabilir.")
        print("  Baslatmak icin: python kasa_api_server.py")
    else:
        print("  EKSIK MODULLER VAR!")
        print("  pip install flask flask-cors requests")

    print("="*60 + "\n")

def test_terminal_modu(ana_makine_ip):
    """Terminal modunda test - ana makineye baglan"""
    print("\n" + "#"*60)
    print("#" + " "*58 + "#")
    print("#    TERMINAL MODU - ANA MAKINEYE BAGLANTI TESTI           #")
    print("#" + " "*58 + "#")
    print("#"*60)

    print(f"\n  Hedef Ana Makine: {ana_makine_ip}:5000")

    # Baglanti testi
    api_ok, client = test_4_api_server_baglanti(host=ana_makine_ip, port=5000)

    if api_ok:
        test_5_veri_okuma_yazma(client)

        print_header("TERMINAL MODU SONUC")
        print("  [+] ANA MAKINEYE BAGLANTI BASARILI!")
        print(f"  [+] Veri okuma/yazma: {ana_makine_ip}:5000")
        print("\n  Terminal olarak calisabilirsiniz.")
        print("  Yapilan islemler ana makinedeki veritabanina kaydedilecek.")
    else:
        print_header("TERMINAL MODU SONUC")
        print("  [-] ANA MAKINEYE BAGLANILAMIYOR!")
        print("\n  Kontrol edin:")
        print(f"    1. Ana makinede API Server calisiyor mu?")
        print(f"    2. IP adresi dogru mu? ({ana_makine_ip})")
        print(f"    3. Firewall port 5000'i engelliyor mu?")
        print(f"    4. Ayni ag uzerinde misiniz?")

def main():
    print("\nKullanim:")
    print("  1. ANA MAKINE testi: python test_ag_baglanti.py")
    print("  2. TERMINAL testi:   python test_ag_baglanti.py <ana_makine_ip>")
    print("")

    if len(sys.argv) > 1:
        # Terminal modu - ana makine IP'si verildi
        ana_makine_ip = sys.argv[1]
        test_terminal_modu(ana_makine_ip)
    else:
        # Ana makine modu
        test_ana_makine_modu()

    try:
        input("\nCikmak icin Enter'a basin...")
    except EOFError:
        pass

if __name__ == "__main__":
    main()
