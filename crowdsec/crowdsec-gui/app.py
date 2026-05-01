from flask import Flask, render_template, request, jsonify
import subprocess
import json
import logging
import urllib.request
import ipaddress
import os
import time
from datetime import datetime
from collections import Counter, defaultdict

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ─── RTBH Feed Ön Bellek ───────────────────────────────────────────────────────
RTBH_FEED_FILE = '/var/cache/cli-rtbh/feed.txt'
_rtbh_networks: list = []
_rtbh_cache_ts: float = 0.0
RTBH_CACHE_TTL = 600  # 10 dakika

def load_rtbh_feed(force: bool = False) -> list:
    """RTBH feed'ini dosyadan yükler, 10 dakika önbellekte tutar."""
    global _rtbh_networks, _rtbh_cache_ts
    if not force and time.monotonic() - _rtbh_cache_ts < RTBH_CACHE_TTL:
        return _rtbh_networks
    try:
        with open(RTBH_FEED_FILE) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        nets = []
        for line in lines:
            try:
                nets.append(ipaddress.ip_network(line, strict=False))
            except ValueError:
                pass
        _rtbh_networks = nets
        _rtbh_cache_ts = time.monotonic()
        logging.info(f'RTBH feed yüklüldü: {len(nets)} kayıt')
    except FileNotFoundError:
        logging.warning(f'RTBH feed dosyası bulunamadı: {RTBH_FEED_FILE}')
    return _rtbh_networks

def check_ip_in_rtbh(ip_str: str):
    """IP'nin RTBH listesinde olup olmadığını kontrol eder. Eşleşen CIDR'i döner."""
    try:
        ip = ipaddress.ip_address(ip_str)
        for net in load_rtbh_feed():
            if ip in net:
                return str(net)
        return None
    except ValueError:
        return None

# ─── GeoIP Ön Bellek (ip-api.com fallback) ──────────────────────────────────
_geo_cache: dict = {}   # ip → country_code

def geo_lookup(ips: list) -> dict:
    """ip-api.com batch API ile eksik ülke bilgilerini tamamlar.
    Ücretşsiz, anahtar gerektirmez, dakikada 45 istek (100 IP/istek).
    Sonuçlar process başlığı boyunca önbelleğe alınır.
    """
    eksik = [ip for ip in ips if ip and ip not in _geo_cache]
    if not eksik:
        return {ip: _geo_cache.get(ip, '') for ip in ips}

    # En fazla 100 IP / istek
    for i in range(0, len(eksik), 100):
        yigin = eksik[i:i + 100]
        try:
            payload = json.dumps(
                [{'query': ip, 'fields': 'query,countryCode'} for ip in yigin]
            ).encode()
            req = urllib.request.Request(
                'http://ip-api.com/batch?fields=query,countryCode',
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                for r in json.loads(resp.read()):
                    _geo_cache[r['query']] = r.get('countryCode', '')
        except Exception as ex:
            logging.warning(f'GeoIP sorgusu başarısız: {ex}')
            for ip in yigin:
                _geo_cache.setdefault(ip, '')

    return {ip: _geo_cache.get(ip, '') for ip in ips}


def ip_detail(ip: str) -> dict:
    """Tek bir IP için ülke, AS adı/numarası ve ISP bilgisini ip-api.com'dan çeker."""
    try:
        url = f'http://ip-api.com/json/{ip}?fields=status,countryCode,country,as,asname'
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get('status') == 'success':
            raw_as = data.get('as', '')            # örn: "AS9121 Turkcell Internet AS"
            as_number = raw_as.split(' ')[0].lstrip('AS') if raw_as else ''
            as_name   = ' '.join(raw_as.split(' ')[1:]) if raw_as else data.get('asname', '')
            return {
                'country_code': data.get('countryCode', ''),
                'country':      data.get('country', ''),
                'as_number':    as_number,
                'as_name':      as_name or data.get('asname', ''),
            }
    except Exception as ex:
        logging.warning(f'ip_detail sorgusu başarısız ({ip}): {ex}')
    return {'country_code': '', 'country': '', 'as_number': '', 'as_name': ''}


def run_cscli(*args):
    """cscli komutunu çalıştırır, (returncode, stdout, stderr) döner."""
    try:
        result = subprocess.run(
            ['sudo', 'cscli'] + list(args),
            capture_output=True, text=True, check=False, timeout=15
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, '', 'Komut zaman aşımına uğradı (15s)'
    except FileNotFoundError:
        raise


# ─── Yardımcı: Yasaklı IP listesi ───────────────────────────────────────────

def get_banned_ips():
    """Şu an yasaklı IP adreslerini döner."""
    try:
        code, out, err = run_cscli('decisions', 'list', '-o', 'json')
        if code != 0:
            logging.error(f"cscli hata: {err}")
            return []
        if not out or out == 'null':
            return []
        banned = []
        for item in json.loads(out):
            for dec in (item.get('decisions') or []):
                if dec.get('type') == 'ban':
                    banned.append({
                        'id':       dec.get('id'),
                        'ip':       dec.get('value'),
                        'reason':   dec.get('scenario'),
                        'duration': dec.get('duration'),
                    })
        return banned
    except FileNotFoundError:
        logging.warning("cscli bulunamadı — örnek veri kullanılıyor.")
        return [
            {'id': 1, 'ip': '192.168.1.55', 'reason': 'open-appsec/malicious-request', 'duration': '4sa'},
            {'id': 2, 'ip': '10.0.0.21',    'reason': 'crowdsec/http-probing',          'duration': '2sa 30dk'},
        ]
    except Exception as e:
        logging.error(f"cscli çıktısı ayrıştırılamadı: {e}")
        return []


# ─── Ana sayfa ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', banned_ips=get_banned_ips())

@app.route('/favicon.ico')
def favicon():
    if os.path.exists(os.path.join(app.root_path, 'static', 'favicon.ico')):
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    return send_from_directory(app.root_path, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# ─── Yasak kaldır ─────────────────────────────────────────────────────────────

@app.route('/unban', methods=['POST'])
def unban_ip():
    ip = (request.get_json() or {}).get('ip', '').strip()
    if not ip:
        return jsonify({'success': False, 'error': 'IP adresi gereklidir'}), 400
    try:
        code, _, err = run_cscli('decisions', 'delete', '-i', ip)
        if code == 0:
            logging.info(f"Yasak kaldırıldı: {ip}")
            return jsonify({'success': True, 'message': f'{ip} adresinin yasağı kaldırıldı.'})
        return jsonify({'success': False, 'error': err}), 500
    except FileNotFoundError:
        return jsonify({'success': True, 'message': f'{ip} adresinin yasağı kaldırıldı. (Test)'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── API: Alertler ────────────────────────────────────────────────────────────

@app.route('/api/alerts')
def api_alerts():
    try:
        code, out, err = run_cscli('alerts', 'list', '-o', 'json', '--limit', '500')
        if code != 0:
            return jsonify({'success': False, 'error': err}), 500
        data = json.loads(out) if (out and out != 'null') else []

        # Aktif CrowdSec ban listesini tek seferlik çek
        banned_set: set = set()
        try:
            bcode, bout, _ = run_cscli('decisions', 'list', '-o', 'json')
            if bcode == 0 and bout and bout != 'null':
                for item in (json.loads(bout) or []):
                    for dec in (item.get('decisions') or []):
                        if dec.get('type') == 'ban':
                            banned_set.add(dec.get('value', ''))
        except Exception:
            pass

        # Her alert için RTBH + CrowdSec durum bilgisi ekle
        for alert in (data or []):
            ip = (alert.get('source') or {}).get('ip', '').strip()
            blocks = []
            if ip:
                if check_ip_in_rtbh(ip):
                    blocks.append('RTBH')
                if ip in banned_set:
                    blocks.append('CROWDSEC')
            alert['blocks'] = blocks

        return jsonify({'success': True, 'data': data or []})
    except FileNotFoundError:
        return jsonify({'success': True, 'data': []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── API: IP Sorgula ─────────────────────────────────────────────────────────

@app.route('/api/query-ip', methods=['POST'])
def api_query_ip():
    ip = (request.get_json() or {}).get('ip', '').strip()
    if not ip:
        return jsonify({'success': False, 'error': 'IP adresi gereklidir'}), 400
    try:
        code, out, err = run_cscli('decisions', 'list', '-i', ip, '-o', 'json')
        if code != 0:
            return jsonify({'success': False, 'error': err}), 500

        # ip-api.com'dan AS + ülke bilgisini zenginleştir
        detail = ip_detail(ip)

        # RTBH feed kontrolü
        rtbh_match = check_ip_in_rtbh(ip)  # eşleşen CIDR veya None

        rows = []
        if out and out != 'null':
            for item in (json.loads(out) or []):
                for dec in (item.get('decisions') or []):
                    rows.append({
                        'ip':        dec.get('value'),
                        'type':      dec.get('type'),
                        'reason':    dec.get('scenario'),
                        'duration':  dec.get('duration'),
                        'origin':    dec.get('origin'),
                        'country':   detail.get('country', ''),
                        'country_code': detail.get('country_code', ''),
                        'as_number': detail.get('as_number', ''),
                        'as_name':   detail.get('as_name', ''),
                    })

        return jsonify({
            'success': True,
            'banned':  len(rows) > 0,
            'rtbh':    rtbh_match,
            'detail':  detail,
            'data':    rows,
        })
    except FileNotFoundError:
        return jsonify({'success': True, 'banned': False, 'rtbh': None, 'detail': {}, 'data': []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── API: AS Sorgusu ──────────────────────────────────────────────────────────

@app.route('/api/query-as', methods=['POST'])
def api_query_as():
    """AS adı veya numarasına göre alert geçmişindeki tüm kaynak IP'leri döner."""
    body     = request.get_json() or {}
    as_term  = body.get('as_name', '').strip().lower()
    if not as_term:
        return jsonify({'success': False, 'error': 'AS adı veya numarası gereklidir'}), 400

    try:
        code, out, err = run_cscli('alerts', 'list', '-o', 'json', '--limit', '1000')
        if code != 0:
            return jsonify({'success': False, 'error': err}), 500

        alerts = json.loads(out) if (out and out != 'null') else []

        matched: dict = {}   # ip → bilgi sözlüğü
        for alert in (alerts or []):
            src     = alert.get('source', {})
            as_name = (src.get('as_name', '') or '').strip()
            as_num  = str(src.get('as_number', '') or '').strip()

            if as_term not in as_name.lower() and as_term not in as_num.lower():
                continue

            ip = src.get('ip', '').strip()
            if not ip:
                continue

            events   = int(alert.get('events_count', 1) or 1)
            scenario = alert.get('scenario', '').strip()

            if ip not in matched:
                matched[ip] = {
                    'ip':        ip,
                    'as_name':   as_name,
                    'as_number': as_num,
                    'country':   src.get('country', '').strip(),
                    'events':    0,
                    'scenarios': set(),
                }
            matched[ip]['events'] += events
            if scenario:
                matched[ip]['scenarios'].add(scenario)

        # Ülke bilgisi eksik olanlar için GeoIP fallback
        eksik = [ip for ip, d in matched.items() if not d['country']]
        if eksik:
            geo = geo_lookup(eksik)
            for ip in eksik:
                matched[ip]['country'] = geo.get(ip, '')

        # ── Aktif engel durumu: CrowdSec kararları (tek seferlik) ──────────────
        banned_set: set = set()
        try:
            bcode, bout, _ = run_cscli('decisions', 'list', '-o', 'json')
            if bcode == 0 and bout and bout != 'null':
                for item in (json.loads(bout) or []):
                    for dec in (item.get('decisions') or []):
                        if dec.get('type') == 'ban':
                            banned_set.add(dec.get('value', ''))
        except Exception:
            pass

        # ── Her IP için RTBH + CrowdSec durumunu ekle ──────────────────────────
        for ip_data in matched.values():
            blocks = []
            if check_ip_in_rtbh(ip_data['ip']):
                blocks.append('RTBH')
            if ip_data['ip'] in banned_set:
                blocks.append('CROWDSEC')
            ip_data['blocks'] = blocks

        result = [
            {**d, 'scenarios': sorted(d['scenarios'])}
            for d in sorted(matched.values(), key=lambda x: -x['events'])
        ]
        return jsonify({'success': True, 'total': len(result), 'data': result})

    except FileNotFoundError:
        return jsonify({'success': True, 'total': 0, 'data': []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── API: RTBH Feed Sorgula ───────────────────────────────────────────────────

@app.route('/api/check-rtbh', methods=['POST'])
def api_check_rtbh():
    """Bir IP'nin CLI RTBH feed'inde olup olmadığını kontrol eder."""
    ip_str = (request.get_json() or {}).get('ip', '').strip()
    if not ip_str:
        return jsonify({'success': False, 'error': 'IP adresi gereklidir'}), 400
    try:
        matched = check_ip_in_rtbh(ip_str)
        return jsonify({
            'success':      True,
            'in_feed':      matched is not None,
            'matched_cidr': matched,
            'ip':           ip_str,
            'feed_size':    len(load_rtbh_feed()),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rtbh-stats')
def api_rtbh_stats():
    """RTBH feed istatistiklerini döner."""
    import re
    try:
        nets     = load_rtbh_feed()
        log_son  = None
        last_update = None

        try:
            with open('/var/log/cli-feed-update.log') as f:
                satirlar = [l.strip() for l in f if l.strip()]

            if satirlar:
                log_son = satirlar[-1]

                # Son "Tamamlandı" satırından doğru zaman damgasını oku
                # Bash date komutu sunucunun TZ ayarına göre yazar → UTC sorununu aşar
                for satir in reversed(satirlar):
                    if 'Tamamland' in satir:
                        m = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', satir)
                        if m:
                            dt = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
                            last_update = dt.strftime('%d.%m.%Y %H:%M')
                        break
        except Exception:
            pass

        return jsonify({
            'success':     True,
            'feed_size':   len(nets),
            'last_update': last_update,
            'log_son':     log_son,
            'feed_file':   RTBH_FEED_FILE,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── API: Sistem İstatistikleri ──────────────────────────────────────────────

def _cpu_percent() -> float:
    """0.15s aralıkla /proc/stat okuyarak anlık CPU % hesaplar."""
    def _read():
        with open('/proc/stat') as f:
            vals = f.readline().split()[1:]
        total = sum(int(v) for v in vals)
        idle  = int(vals[3])
        return total, idle
    t1, i1 = _read(); time.sleep(0.15); t2, i2 = _read()
    dt = t2 - t1
    return round((1 - (i2 - i1) / dt) * 100, 1) if dt else 0.0

def _mem_info() -> dict:
    info = {}
    with open('/proc/meminfo') as f:
        for line in f:
            k, v = line.split(':')
            info[k.strip()] = int(v.strip().split()[0]) * 1024
    total = info.get('MemTotal', 0)
    avail = info.get('MemAvailable', 0)
    used  = total - avail
    return {'total': total, 'used': used, 'free': avail,
            'percent': round(used / total * 100, 1) if total else 0}

def _disk_info(path: str = '/') -> dict:
    import shutil
    u = shutil.disk_usage(path)
    return {'total': u.total, 'used': u.used, 'free': u.free,
            'percent': round(u.used / u.total * 100, 1) if u.total else 0}

def _log_sizes() -> list:
    def dir_size(path, use_sudo=False):
        cmd = ['sudo', 'du', '-sb', path] if use_sudo else ['du', '-sb', path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return int(r.stdout.split()[0]) if r.returncode == 0 else None

    entries = [
        # (label, path, type, use_sudo)
        ('Nginx',        '/var/log/nginx',                         'dir',  False),
        ('open-appsec',  '/var/log/nano_agent',                    'dir',  True),   # root dizini
        ('Gunicorn',     '/var/log/gunicorn',                      'dir',  False),
        ('CrowdSec API', '/var/log/crowdsec_api.log',              'file', False),
        ('CrowdSec',     '/var/log/crowdsec.log',                  'file', False),
        ('CrowdSec Bouncer', '/var/log/crowdsec-firewall-bouncer.log', 'file', False),
        ('CLI RTBH Feed','/var/log/cli-feed-update.log',           'file', False),
        ('Syslog',       '/var/log/syslog',                        'file', False),
        ('Auth',         '/var/log/auth.log',                      'file', False),
    ]
    rows = []
    for name, path, kind, use_sudo in entries:
        try:
            size = dir_size(path, use_sudo) if kind == 'dir' else os.path.getsize(path)
            rows.append({'name': name, 'path': path, 'size': size, 'type': kind})
        except Exception:
            rows.append({'name': name, 'path': path, 'size': None, 'type': kind})
    return rows

def _svc_status(name: str) -> str:
    try:
        r = subprocess.run(['systemctl', 'is-active', name],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip()
    except Exception:
        return 'unknown'


@app.route('/api/system-stats')
def api_system_stats():
    try:
        services = [
            {'name': 'nginx',                  'status': _svc_status('nginx')},
            {'name': 'crowdsec',               'status': _svc_status('crowdsec')},
            {'name': 'crowdsec-firewall-bouncer','status': _svc_status('crowdsec-firewall-bouncer')},
            {'name': 'crowdsec-gui',           'status': _svc_status('crowdsec-gui')},
            {'name': 'cli-feed-update.timer',  'status': _svc_status('cli-feed-update.timer')},
        ]
        return jsonify({
            'success':  True,
            'cpu':      _cpu_percent(),
            'mem':      _mem_info(),
            'disk':     _disk_info('/'),
            'logs':     _log_sizes(),
            'services': services,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── API: Metrikler ───────────────────────────────────────────────────────────

@app.route('/api/metrics')
def api_metrics():
    try:
        code, out, err = run_cscli('metrics', 'show', '-o', 'json')
        if code != 0:
            # Eski sürüm denemesi
            code, out, err = run_cscli('metrics', '-o', 'json')
        if code != 0:
            return jsonify({'success': False, 'error': err}), 500
        data = json.loads(out) if out else {}
        return jsonify({'success': True, 'data': data})
    except FileNotFoundError:
        return jsonify({'success': True, 'data': {
            'acquisition': {'/var/log/nginx/access.log': {'reads': 1024, 'lines_parsed': 890, 'lines_unparsed': 134, 'lines_sent': 890}},
            'parsers':     {'crowdsec/nginx': {'hits': 890, 'parsed': 780, 'unparsed': 110}},
            'buckets':     {'crowdsec/http-probing': {'curr_count': 2, 'overflow': 12, 'pour': 45}},
        }})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── API: Bouncerlar ──────────────────────────────────────────────────────────

@app.route('/api/bouncers')
def api_bouncers():
    try:
        code, out, err = run_cscli('bouncers', 'list', '-o', 'json')
        if code != 0:
            return jsonify({'success': False, 'error': err}), 500
        data = json.loads(out) if (out and out != 'null') else []
        return jsonify({'success': True, 'data': data or []})
    except FileNotFoundError:
        return jsonify({'success': True, 'data': [
            {'name': 'cs-firewall-bouncer-iptables', 'ip_address': '127.0.0.1',
             'last_pull': '2026-04-28T22:55:00Z', 'type': 'cs-firewall-bouncer',
             'version': 'v0.0.28', 'auth_type': 'api-key'},
        ]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── API: İstatistikler (Top N) ───────────────────────────────────────────────

@app.route('/api/stats')
def api_stats():
    """Alert verisinden Top 10 ülke, senaryo, AS ve kaynak IP hesaplar."""
    def top_n(counter, n=10):
        total = sum(counter.values())
        return [
            {'name': k, 'count': v, 'pct': round(v / total * 100, 1) if total else 0}
            for k, v in counter.most_common(n)
        ]

    try:
        code, out, err = run_cscli('alerts', 'list', '-o', 'json', '--limit', '500')
        if code != 0:
            return jsonify({'success': False, 'error': err}), 500

        data = json.loads(out) if (out and out != 'null') else []

        countries  = Counter()
        scenarios  = Counter()
        as_names   = Counter()
        source_ips = Counter()
        as_ip_map  = defaultdict(Counter)  # AS adı → {ip: sayı}

        for alert in (data or []):
            src    = alert.get('source', {})
            events = int(alert.get('events_count', 1) or 1)
            country  = src.get('country', '').strip()
            as_name  = src.get('as_name',  '').strip()
            ip       = src.get('ip',        '').strip()
            scenario = alert.get('scenario', '').strip()

            if as_name:  as_names[as_name]    += events
            if ip:       source_ips[ip]        += events
            if scenario: scenarios[scenario]   += events
            if as_name and ip:
                as_ip_map[as_name][ip] += events

        # CrowdSec'ten country bilgisi gelmiyorsa ip-api.com ile tamamla
        all_ips = [a.get('source', {}).get('ip', '').strip() for a in (data or [])]
        all_ips = list({ip for ip in all_ips if ip})
        geo_map = geo_lookup(all_ips)

        for alert in (data or []):
            src    = alert.get('source', {})
            events = int(alert.get('events_count', 1) or 1)
            ip     = src.get('ip', '').strip()
            # CrowdSec'in kendi country'si önce dene, yoksa fallback
            country = src.get('country', '').strip() or geo_map.get(ip, '')
            if country:
                countries[country] += events

        def top_n_as(counter, ip_map, n=10):
            total = sum(counter.values())
            result = []
            for k, v in counter.most_common(n):
                top_ips = [ip for ip, _ in ip_map.get(k, Counter()).most_common(3)]
                result.append({
                    'name': k, 'count': v,
                    'pct': round(v / total * 100, 1) if total else 0,
                    'ips': top_ips
                })
            return result

        return jsonify({
            'success':    True,
            'countries':  top_n(countries),
            'scenarios':  top_n(scenarios),
            'as_names':   top_n_as(as_names, as_ip_map),
            'source_ips': top_n(source_ips),
        })

    except FileNotFoundError:
        return jsonify({'success': True,
            'countries':  [{'name': 'US', 'count': 98, 'pct': 22.9}, {'name': 'CN', 'count': 63, 'pct': 14.6}],
            'scenarios':  [{'name': 'crowdsecurity/http-probing', 'count': 135, 'pct': 21.9}],
            'as_names':   [{'name': 'AMAZON-02', 'count': 35, 'pct': 8.1}],
            'source_ips': [{'name': '1.2.3.4', 'count': 12, 'pct': 5.5}],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Gunicorn ile çalışırken bu blok hiç çalışmaz.
    # Yalnızca "python app.py" ile yerel test için kullanılır.
    app.run(host='0.0.0.0', port=5001, debug=False)
