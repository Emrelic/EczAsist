"""
Botanik Bot - Kasa API Server
Ana makine üzerinde çalışan REST API sunucusu
Terminal makineler bu API üzerinden veri okur/yazar
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

# Veritabanı yolu
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = Path(SCRIPT_DIR) / "kasa_veritabani.db"


def get_db_connection():
    """Veritabanı bağlantısı al"""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Veritabanı tablolarını oluştur"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Kasa kapatma tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kasa_gunluk (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT NOT NULL UNIQUE,
            baslangic_kasasi REAL DEFAULT 0,
            baslangic_kupurler_json TEXT,
            sayim_toplam REAL DEFAULT 0,
            sayim_kupurler_json TEXT,
            pos_toplam REAL DEFAULT 0,
            pos_detay_json TEXT,
            iban_toplam REAL DEFAULT 0,
            iban_detay_json TEXT,
            masraf_toplam REAL DEFAULT 0,
            masraf_detay_json TEXT,
            silinen_etki_toplam REAL DEFAULT 0,
            silinen_detay_json TEXT,
            alinan_para_toplam REAL DEFAULT 0,
            alinan_detay_json TEXT,
            botanik_nakit REAL DEFAULT 0,
            botanik_pos REAL DEFAULT 0,
            botanik_iban REAL DEFAULT 0,
            botanik_genel_toplam REAL DEFAULT 0,
            nakit_toplam REAL DEFAULT 0,
            genel_toplam REAL DEFAULT 0,
            son_genel_toplam REAL DEFAULT 0,
            fark REAL DEFAULT 0,
            fark_kontrol_yapildi INTEGER DEFAULT 0,
            fark_kontrol_json TEXT,
            ertesi_gun_kasasi REAL DEFAULT 0,
            ertesi_gun_kupurler_json TEXT,
            ayrilan_para REAL DEFAULT 0,
            ayrilan_kupurler_json TEXT,
            wizard_tamamlandi INTEGER DEFAULT 0,
            wizard_adim INTEGER DEFAULT 0,
            durum TEXT DEFAULT 'devam_ediyor',
            olusturma_zamani TEXT NOT NULL,
            guncelleme_zamani TEXT
        )
    ''')

    # Kasa geçmişi tablosu (arşiv)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kasa_arsiv (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gunluk_id INTEGER,
            tarih TEXT NOT NULL,
            ozet_json TEXT,
            rapor_metni TEXT,
            olusturma_zamani TEXT NOT NULL,
            FOREIGN KEY (gunluk_id) REFERENCES kasa_gunluk(id)
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("Veritabanı tabloları oluşturuldu")


# API Endpoints

@app.route('/api/health', methods=['GET'])
def health_check():
    """Sunucu sağlık kontrolü"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'server': 'Botanik Kasa API'
    })


@app.route('/api/kasa/bugun', methods=['GET'])
def bugunun_kasasi():
    """Bugünün kasa verisini getir"""
    tarih = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM kasa_gunluk WHERE tarih = ?', (tarih,))
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
            'data': None,
            'message': 'Bugun icin kayit yok'
        })


@app.route('/api/kasa/tarih/<tarih>', methods=['GET'])
def tarihe_gore_kasa(tarih):
    """Belirli bir tarihin kasa verisini getir"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM kasa_gunluk WHERE tarih = ?', (tarih,))
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
            'message': f'{tarih} icin kayit bulunamadi'
        })


@app.route('/api/kasa/kaydet', methods=['POST'])
def kasa_kaydet():
    """Kasa verisini kaydet veya güncelle"""
    try:
        data = request.get_json()
        tarih = data.get('tarih', datetime.now().strftime("%Y-%m-%d"))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Mevcut kayıt var mı kontrol et
        cursor.execute('SELECT id FROM kasa_gunluk WHERE tarih = ?', (tarih,))
        existing = cursor.fetchone()

        if existing:
            # Güncelle
            update_fields = []
            update_values = []

            for key, value in data.items():
                if key != 'tarih' and key != 'id':
                    update_fields.append(f"{key} = ?")
                    if isinstance(value, (dict, list)):
                        update_values.append(json.dumps(value, ensure_ascii=False))
                    else:
                        update_values.append(value)

            update_fields.append("guncelleme_zamani = ?")
            update_values.append(datetime.now().isoformat())
            update_values.append(tarih)

            query = f"UPDATE kasa_gunluk SET {', '.join(update_fields)} WHERE tarih = ?"
            cursor.execute(query, update_values)

            message = "Kasa verisi guncellendi"
        else:
            # Yeni kayıt
            columns = ['tarih', 'olusturma_zamani']
            values = [tarih, datetime.now().isoformat()]

            for key, value in data.items():
                if key != 'tarih':
                    columns.append(key)
                    if isinstance(value, (dict, list)):
                        values.append(json.dumps(value, ensure_ascii=False))
                    else:
                        values.append(value)

            placeholders = ', '.join(['?' for _ in columns])
            query = f"INSERT INTO kasa_gunluk ({', '.join(columns)}) VALUES ({placeholders})"
            cursor.execute(query, values)

            message = "Yeni kasa kaydi olusturuldu"

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': message
        })

    except Exception as e:
        logger.error(f"Kasa kaydetme hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/kasa/wizard/adim', methods=['POST'])
def wizard_adim_kaydet():
    """Wizard adımını kaydet"""
    try:
        data = request.get_json()
        tarih = data.get('tarih', datetime.now().strftime("%Y-%m-%d"))
        adim = data.get('adim', 0)
        adim_verisi = data.get('veri', {})

        conn = get_db_connection()
        cursor = conn.cursor()

        # Mevcut kaydı kontrol et veya oluştur
        cursor.execute('SELECT id, wizard_adim FROM kasa_gunluk WHERE tarih = ?', (tarih,))
        existing = cursor.fetchone()

        if not existing:
            cursor.execute('''
                INSERT INTO kasa_gunluk (tarih, wizard_adim, olusturma_zamani)
                VALUES (?, ?, ?)
            ''', (tarih, adim, datetime.now().isoformat()))
            conn.commit()

        # Adım verisini güncelle
        update_query = "UPDATE kasa_gunluk SET wizard_adim = ?, guncelleme_zamani = ?"
        update_values = [adim, datetime.now().isoformat()]

        # Adıma göre ilgili alanları güncelle
        for key, value in adim_verisi.items():
            if isinstance(value, (dict, list)):
                update_query += f", {key} = ?"
                update_values.append(json.dumps(value, ensure_ascii=False))
            else:
                update_query += f", {key} = ?"
                update_values.append(value)

        update_query += " WHERE tarih = ?"
        update_values.append(tarih)

        cursor.execute(update_query, update_values)
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Adim {adim} kaydedildi'
        })

    except Exception as e:
        logger.error(f"Wizard adım kaydetme hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/kasa/onceki-gun', methods=['GET'])
def onceki_gun_kasasi():
    """Bir önceki günün ertesi gün kasasını getir"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT ertesi_gun_kasasi, ertesi_gun_kupurler_json, tarih
        FROM kasa_gunluk
        WHERE durum = 'tamamlandi'
        ORDER BY tarih DESC
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

        return jsonify({
            'success': True,
            'data': {
                'toplam': row['ertesi_gun_kasasi'],
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
        SELECT id, tarih, baslangic_kasasi, sayim_toplam, pos_toplam, iban_toplam,
               masraf_toplam, silinen_etki_toplam, alinan_para_toplam,
               genel_toplam, son_genel_toplam, botanik_genel_toplam, fark,
               ertesi_gun_kasasi, ayrilan_para, durum
        FROM kasa_gunluk
        ORDER BY tarih DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))

    rows = cursor.fetchall()

    # Toplam kayıt sayısı
    cursor.execute('SELECT COUNT(*) FROM kasa_gunluk')
    total = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'success': True,
        'data': [dict(row) for row in rows],
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.route('/api/kasa/arsivle', methods=['POST'])
def kasa_arsivle():
    """Günlük kasa verisini arşivle"""
    try:
        data = request.get_json()
        tarih = data.get('tarih')

        if not tarih:
            return jsonify({
                'success': False,
                'error': 'Tarih gerekli'
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Günlük kaydı al
        cursor.execute('SELECT * FROM kasa_gunluk WHERE tarih = ?', (tarih,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Kayit bulunamadi'
            }), 404

        # Özet oluştur
        ozet = {
            'baslangic_kasasi': row['baslangic_kasasi'],
            'sayim_toplam': row['sayim_toplam'],
            'pos_toplam': row['pos_toplam'],
            'iban_toplam': row['iban_toplam'],
            'genel_toplam': row['genel_toplam'],
            'son_genel_toplam': row['son_genel_toplam'],
            'botanik_genel_toplam': row['botanik_genel_toplam'],
            'fark': row['fark'],
            'ertesi_gun_kasasi': row['ertesi_gun_kasasi'],
            'ayrilan_para': row['ayrilan_para']
        }

        # Arşive ekle
        cursor.execute('''
            INSERT INTO kasa_arsiv (gunluk_id, tarih, ozet_json, olusturma_zamani)
            VALUES (?, ?, ?, ?)
        ''', (row['id'], tarih, json.dumps(ozet, ensure_ascii=False), datetime.now().isoformat()))

        # Durumu güncelle
        cursor.execute('''
            UPDATE kasa_gunluk SET durum = 'tamamlandi', wizard_tamamlandi = 1
            WHERE tarih = ?
        ''', (tarih,))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Kasa arsivlendi'
        })

    except Exception as e:
        logger.error(f"Arşivleme hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def run_server(host='0.0.0.0', port=5000):
    """API sunucusunu başlat"""
    init_database()
    logger.info(f"Kasa API sunucusu başlatılıyor: http://{host}:{port}")
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
    return server_thread


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Botanik Kasa API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host adresi')
    parser.add_argument('--port', type=int, default=5000, help='Port numarası')

    args = parser.parse_args()
    run_server(args.host, args.port)
