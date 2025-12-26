"""
Botanik Bot - Kasa API Server
Ana makine üzerinde çalışan REST API sunucusu
Terminal makineler bu API üzerinden veri okur/yazar
Veritabanı: AppData/BotanikKasa/oturum_raporlari.db (ana uygulama ile aynı)
"""

import json
import sqlite3
import os
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Veritabanı yolu - Ana uygulama ile AYNI veritabanı
def get_db_path():
    """Ana uygulama ile aynı veritabanı yolunu döndür"""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    db_klasor = Path(appdata) / "BotanikKasa"
    db_klasor.mkdir(parents=True, exist_ok=True)
    return db_klasor / "oturum_raporlari.db"

DB_PATH = None  # Lazy initialization


def get_db_connection():
    """Veritabanı bağlantısı al"""
    global DB_PATH
    if DB_PATH is None:
        DB_PATH = get_db_path()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Veritabanı tablolarını oluştur - Ana uygulama ile AYNI şema"""
    global DB_PATH
    DB_PATH = get_db_path()

    conn = get_db_connection()
    cursor = conn.cursor()

    # kasa_kapatma tablosu - Ana uygulama ile AYNI
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kasa_kapatma (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT NOT NULL,
            saat TEXT NOT NULL,
            baslangic_kasasi REAL DEFAULT 0,
            baslangic_kupurler_json TEXT,
            sayim_toplam REAL DEFAULT 0,
            pos_toplam REAL DEFAULT 0,
            iban_toplam REAL DEFAULT 0,
            masraf_toplam REAL DEFAULT 0,
            silinen_etki_toplam REAL DEFAULT 0,
            gun_ici_alinan_toplam REAL DEFAULT 0,
            nakit_toplam REAL DEFAULT 0,
            genel_toplam REAL DEFAULT 0,
            son_genel_toplam REAL DEFAULT 0,
            botanik_nakit REAL DEFAULT 0,
            botanik_pos REAL DEFAULT 0,
            botanik_iban REAL DEFAULT 0,
            botanik_genel_toplam REAL DEFAULT 0,
            fark REAL DEFAULT 0,
            ertesi_gun_kasasi REAL DEFAULT 0,
            ertesi_gun_kupurler_json TEXT,
            ayrilan_para REAL DEFAULT 0,
            ayrilan_kupurler_json TEXT,
            manuel_baslangic_tutar REAL DEFAULT 0,
            manuel_baslangic_aciklama TEXT,
            detay_json TEXT,
            olusturma_zamani TEXT NOT NULL
        )
    ''')

    # Eksik kolonları kontrol et ve ekle (eski veritabanları için)
    cursor.execute("PRAGMA table_info(kasa_kapatma)")
    mevcut_kolonlar = {col[1] for col in cursor.fetchall()}

    eksik_kolonlar = [
        ("saat", "TEXT DEFAULT '00:00:00'"),
        ("nakit_toplam", "REAL DEFAULT 0"),
        ("ayrilan_para", "REAL DEFAULT 0"),
        ("ayrilan_kupurler_json", "TEXT"),
        ("manuel_baslangic_tutar", "REAL DEFAULT 0"),
        ("manuel_baslangic_aciklama", "TEXT"),
        ("detay_json", "TEXT"),
        ("ertesi_gun_kupurler_json", "TEXT"),
        ("baslangic_kupurler_json", "TEXT"),
        ("gun_ici_alinan_toplam", "REAL DEFAULT 0"),
        ("olusturma_zamani", "TEXT"),
        ("baslangic_kasasi", "REAL DEFAULT 0"),
        ("sayim_toplam", "REAL DEFAULT 0"),
        ("pos_toplam", "REAL DEFAULT 0"),
        ("iban_toplam", "REAL DEFAULT 0"),
        ("masraf_toplam", "REAL DEFAULT 0"),
        ("silinen_etki_toplam", "REAL DEFAULT 0"),
        ("genel_toplam", "REAL DEFAULT 0"),
        ("son_genel_toplam", "REAL DEFAULT 0"),
        ("botanik_nakit", "REAL DEFAULT 0"),
        ("botanik_pos", "REAL DEFAULT 0"),
        ("botanik_iban", "REAL DEFAULT 0"),
        ("botanik_genel_toplam", "REAL DEFAULT 0"),
        ("fark", "REAL DEFAULT 0"),
        ("ertesi_gun_kasasi", "REAL DEFAULT 0"),
    ]

    for kolon_adi, kolon_tipi in eksik_kolonlar:
        if kolon_adi not in mevcut_kolonlar:
            try:
                cursor.execute(f"ALTER TABLE kasa_kapatma ADD COLUMN {kolon_adi} {kolon_tipi}")
                logger.info(f"Eksik kolon eklendi: {kolon_adi}")
            except Exception as e:
                logger.warning(f"Kolon eklenemedi {kolon_adi}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"Veritabanı hazır: {DB_PATH}")


# API Endpoints

@app.route('/api/health', methods=['GET'])
def health_check():
    """Sunucu sağlık kontrolü"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'server': 'Botanik Kasa API',
        'db_path': str(DB_PATH)
    })


@app.route('/api/kasa/kaydet', methods=['POST'])
def kasa_kaydet():
    """Kasa verisini kaydet"""
    try:
        data = request.get_json()
        tarih = data.get('tarih', datetime.now().strftime("%Y-%m-%d"))
        saat = data.get('saat', datetime.now().strftime("%H:%M:%S"))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Yeni kayıt ekle
        cursor.execute('''
            INSERT INTO kasa_kapatma (
                tarih, saat, baslangic_kasasi, baslangic_kupurler_json,
                sayim_toplam, pos_toplam, iban_toplam,
                masraf_toplam, silinen_etki_toplam, gun_ici_alinan_toplam,
                nakit_toplam, genel_toplam, son_genel_toplam,
                botanik_nakit, botanik_pos, botanik_iban, botanik_genel_toplam,
                fark, ertesi_gun_kasasi, ertesi_gun_kupurler_json,
                ayrilan_para, ayrilan_kupurler_json,
                manuel_baslangic_tutar, manuel_baslangic_aciklama,
                detay_json, olusturma_zamani
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tarih, saat,
            data.get('baslangic_kasasi', 0),
            data.get('baslangic_kupurler_json', '{}'),
            data.get('sayim_toplam', 0),
            data.get('pos_toplam', 0),
            data.get('iban_toplam', 0),
            data.get('masraf_toplam', 0),
            data.get('silinen_etki_toplam', 0),
            data.get('gun_ici_alinan_toplam', data.get('alinan_para_toplam', 0)),
            data.get('nakit_toplam', 0),
            data.get('genel_toplam', 0),
            data.get('son_genel_toplam', 0),
            data.get('botanik_nakit', 0),
            data.get('botanik_pos', 0),
            data.get('botanik_iban', 0),
            data.get('botanik_genel_toplam', 0),
            data.get('fark', 0),
            data.get('ertesi_gun_kasasi', 0),
            data.get('ertesi_gun_kupurler_json', '{}'),
            data.get('ayrilan_para', 0),
            data.get('ayrilan_kupurler_json', '{}'),
            data.get('manuel_baslangic_tutar', 0),
            data.get('manuel_baslangic_aciklama', ''),
            data.get('detay_json', '{}'),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        kayit_id = cursor.lastrowid
        conn.close()

        logger.info(f"Kasa kaydedildi: {tarih} - ID: {kayit_id}")
        return jsonify({
            'success': True,
            'message': 'Kasa verisi kaydedildi',
            'id': kayit_id
        })

    except Exception as e:
        import traceback
        hata_detay = traceback.format_exc()
        logger.error(f"Kasa kaydetme hatası: {e}\n{hata_detay}")
        return jsonify({
            'success': False,
            'error': str(e),
            'detay': hata_detay
        }), 500


@app.route('/api/kasa/onceki-gun', methods=['GET'])
def onceki_gun_kasasi():
    """Bir önceki kapatmadan ertesi gün kasasını getir"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT ertesi_gun_kasasi, ertesi_gun_kupurler_json, detay_json, tarih
        FROM kasa_kapatma
        ORDER BY id DESC
        LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()

    if row:
        kupurler = {}
        if row['ertesi_gun_kupurler_json']:
            try:
                kupurler = json.loads(row['ertesi_gun_kupurler_json'])
            except json.JSONDecodeError:
                pass

        # Eski format desteği
        if not kupurler and row['detay_json']:
            try:
                detay = json.loads(row['detay_json'])
                kupurler = detay.get("sayim", {})
            except json.JSONDecodeError:
                pass

        return jsonify({
            'success': True,
            'data': {
                'toplam': row['ertesi_gun_kasasi'] or 0,
                'kupurler': kupurler,
                'tarih': row['tarih']
            }
        })
    else:
        return jsonify({
            'success': True,
            'data': {
                'toplam': 0,
                'kupurler': {},
                'tarih': None
            }
        })


@app.route('/api/kasa/gecmis', methods=['GET'])
def kasa_gecmisi():
    """Kasa geçmişini getir"""
    limit = request.args.get('limit', 30, type=int)
    offset = request.args.get('offset', 0, type=int)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, tarih, saat, baslangic_kasasi, sayim_toplam, pos_toplam, iban_toplam,
               masraf_toplam, silinen_etki_toplam, gun_ici_alinan_toplam,
               nakit_toplam, genel_toplam, son_genel_toplam,
               botanik_nakit, botanik_pos, botanik_iban, botanik_genel_toplam,
               fark, ertesi_gun_kasasi, ayrilan_para, olusturma_zamani
        FROM kasa_kapatma
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))

    rows = cursor.fetchall()

    # Toplam kayıt sayısı
    cursor.execute('SELECT COUNT(*) FROM kasa_kapatma')
    total = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'success': True,
        'data': [dict(row) for row in rows],
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.route('/api/kasa/detay/<int:kayit_id>', methods=['GET'])
def kasa_detay(kayit_id):
    """Belirli bir kaydın detayını getir"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM kasa_kapatma WHERE id = ?', (kayit_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify({
            'success': True,
            'data': dict(row)
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Kayit bulunamadi'
        }), 404


@app.route('/api/kasa/tarih/<tarih>', methods=['GET'])
def tarihe_gore_kasa(tarih):
    """Belirli bir tarihin kasa kayıtlarını getir"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM kasa_kapatma
        WHERE tarih = ?
        ORDER BY id DESC
    ''', (tarih,))
    rows = cursor.fetchall()
    conn.close()

    return jsonify({
        'success': True,
        'data': [dict(row) for row in rows]
    })


@app.route('/api/kasa/son-kayit', methods=['GET'])
def son_kayit():
    """En son kaydı getir"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM kasa_kapatma ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify({
            'success': True,
            'data': dict(row)
        })
    else:
        return jsonify({
            'success': True,
            'data': None
        })


def run_server(host='0.0.0.0', port=5000):
    """API sunucusunu başlat"""
    init_database()
    logger.info(f"Kasa API sunucusu başlatılıyor: http://{host}:{port}")
    logger.info(f"Veritabanı: {DB_PATH}")
    app.run(host=host, port=port, debug=False, threaded=True)


def start_server_thread(host='0.0.0.0', port=5000):
    """API sunucusunu ayrı bir thread'de başlat"""
    init_database()
    server_thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, threaded=True),
        daemon=True
    )
    server_thread.start()
    logger.info(f"Kasa API sunucusu thread olarak başlatıldı: http://{host}:{port}")
    logger.info(f"Veritabanı: {DB_PATH}")
    return server_thread


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Botanik Kasa API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host adresi')
    parser.add_argument('--port', type=int, default=5000, help='Port numarası')

    args = parser.parse_args()
    run_server(args.host, args.port)
