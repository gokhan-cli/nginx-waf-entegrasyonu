from flask import Flask, render_template, request, jsonify
import subprocess
import json
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


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
        code, out, err = run_cscli('alerts', 'list', '-o', 'json', '--limit', '50')
        if code != 0:
            return jsonify({'success': False, 'error': err}), 500
        data = json.loads(out) if (out and out != 'null') else []
        return jsonify({'success': True, 'data': data or []})
    except FileNotFoundError:
        return jsonify({'success': True, 'data': [
            {'id': 1, 'scenario': 'crowdsec/http-probing',          'source': {'ip': '45.32.1.1',    'country': 'CN'}, 'events_count': 15, 'created_at': '2026-04-28T22:00:00Z', 'remediation': True},
            {'id': 2, 'scenario': 'open-appsec/malicious-request',  'source': {'ip': '192.168.5.99', 'country': 'RU'}, 'events_count': 3,  'created_at': '2026-04-28T21:30:00Z', 'remediation': True},
        ]})
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
        rows = []
        if out and out != 'null':
            for item in (json.loads(out) or []):
                for dec in (item.get('decisions') or []):
                    rows.append({
                        'ip':       dec.get('value'),
                        'type':     dec.get('type'),
                        'reason':   dec.get('scenario'),
                        'duration': dec.get('duration'),
                        'origin':   dec.get('origin'),
                    })
        return jsonify({'success': True, 'banned': len(rows) > 0, 'data': rows})
    except FileNotFoundError:
        return jsonify({'success': True, 'banned': False, 'data': []})
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
