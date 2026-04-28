# Nginx 1.29.4 Kurulum ve Yapılandırma Kılavuzu

> **Sürüm:** `nginx=1.29.4-1~noble`  
> **Platform:** Ubuntu 24.04 LTS (Noble Numbat)  
> **Nginx Dalı:** Mainline (Kararlı geliştirme)

---

## İçindekiler

1. [Gereksinimler](#1-gereksinimler)
2. [Resmi Nginx Deposu Ekleme](#2-resmi-nginx-deposu-ekleme)
3. [Kurulum](#3-kurulum)
4. [Servis Yönetimi](#4-servis-yönetimi)
5. [Dizin Yapısı](#5-dizin-yapısı)
6. [Temel Yapılandırma](#6-temel-yapılandırma)
7. [Sanal Sunucu (Server Block) Oluşturma](#7-sanal-sunucu-server-block-oluşturma)
8. [SSL/TLS Yapılandırması](#8-ssltls-yapılandırması)
9. [Güvenlik Sertleştirme](#9-güvenlik-sertleştirme)
10. [Performans Ayarları](#10-performans-ayarları)
11. [Log Yönetimi](#11-log-yönetimi)
12. [Güncelleme ve Kaldırma](#12-güncelleme-ve-kaldırma)
13. [Sık Kullanılan Komutlar](#13-sık-kullanılan-komutlar)
14. [Sorun Giderme](#14-sorun-giderme)

---

## 1. Gereksinimler

```bash
# Sistem güncellemesi
sudo apt update && sudo apt upgrade -y

# Gerekli paketler
sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring
```

**Minimum sistem gereksinimleri:**

| Kaynak   | Minimum | Önerilen |
|----------|---------|----------|
| CPU      | 1 vCPU  | 2+ vCPU  |
| RAM      | 512 MB  | 1+ GB    |
| Disk     | 1 GB    | 10+ GB   |
| OS       | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |

---

## 2. Resmi Nginx Deposu Ekleme

> ⚠️ Ubuntu'nun varsayılan deposundaki Nginx sürümü eskidir. `1.29.4` sürümü için **nginx.org'un resmi deposu** kullanılmalıdır.

```bash
# Nginx imza anahtarını indir ve ekle
curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null

# Anahtarı doğrula
gpg --dry-run --quiet --no-keyring \
    --import --import-options import-show \
    /usr/share/keyrings/nginx-archive-keyring.gpg
```

**Beklenen çıktı (parmak izi doğrulaması):**
```
pub   rsa2048 2011-08-19 [SC] [expires: 2027-05-24]
      573BFD6B3D8FBC641079A6ABABF5BD827BD9BF62
uid           nginx signing key <signing-key@nginx.com>
```

```bash
# Mainline deposunu ekle
echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
http://nginx.org/packages/mainline/ubuntu noble nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list

# Depo önceliğini ayarla (resmi nginx deposu > Ubuntu deposu)
echo -e "Package: *\nPin: origin nginx.org\nPin: release o=nginx\nPin-Priority: 900\n" \
    | sudo tee /etc/apt/preferences.d/99nginx

# Depo listesini güncelle
sudo apt update
```

---

## 3. Kurulum

```bash
# Belirli sürümü kur
sudo apt install nginx=1.29.4-1~noble -y

# Sürümü doğrula
nginx -v
# nginx version: nginx/1.29.4

# Tam derleme bilgisi
nginx -V
```

### Sürümü Sabitleme (Otomatik Güncellemeyi Engelle)

```bash
# Bu sürümü pinn'le — apt upgrade sırasında güncellenmez
sudo apt-mark hold nginx
sudo apt-mark hold nginx-common

# Sabitlenen paketleri kontrol et
apt-mark showhold
```

```bash
# NOT: openappsec entegrasyonunda desteklenen en yüksek nginx sürümü şu an için 1.29.4
# olduğundan dolayı bu sürümü yüklememiz gerekiyor.
# Aşağıdaki link üzerinden desteklenen nginx sürümlerini görebilirsiniz.
```
<https://downloads.openappsec.io/packages/supported-nginx.txt>
---

## 4. Servis Yönetimi

```bash
# Servisi başlat
sudo systemctl start nginx

# Sistem başlangıcında otomatik başlat
sudo systemctl enable nginx

# Servis durumu
sudo systemctl status nginx

# Yeniden başlat (konfigürasyon değişikliğinden sonra)
sudo systemctl restart nginx

# Graceful reload (bağlantıları kesmeden)
sudo systemctl reload nginx
# veya
sudo nginx -s reload

# Durdur
sudo systemctl stop nginx
```

---

## 5. Dizin Yapısı

```
/etc/nginx/
├── nginx.conf              # Ana konfigürasyon dosyası
├── conf.d/                 # Ek konfigürasyon dosyaları (.conf)
│   └── default.conf        # Varsayılan sunucu bloğu
├── modules-enabled/        # Etkin modüller
├── modules-available/      # Mevcut modüller
└── mime.types              # MIME tür tanımları

/var/log/nginx/
├── access.log              # Erişim logları
└── error.log               # Hata logları

/var/cache/nginx/           # Nginx önbelleği
/usr/share/nginx/html/      # Varsayılan web dizini
/run/nginx.pid              # PID dosyası
```

---

## 6. Temel Yapılandırma

```bash
sudo nano /etc/nginx/nginx.conf
```

```nginx
user  nginx;

# CPU çekirdek sayısı kadar worker (auto = otomatik algıla)
worker_processes  auto;

error_log  /var/log/nginx/error.log notice;
pid        /run/nginx.pid;

# Açık dosya tanımlayıcı limiti (ulimit -n ile eşleşmeli)
worker_rlimit_nofile 65535;

events {
    # Her worker için maksimum bağlantı
    worker_connections  4096;

    # Linux'ta en performanslı yöntem
    use epoll;

    # Aynı anda birden fazla bağlantı kabul et
    multi_accept on;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # Nginx versiyon bilgisini gizle
    server_tokens off;

    # Log formatı
    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';

    access_log  /var/log/nginx/access.log  main;

    # Performans
    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;

    # Bağlantı zaman aşımları
    keepalive_timeout  65;
    keepalive_requests 1000;

    # Buffer boyutları
    client_body_buffer_size      128k;
    client_max_body_size         50m;
    client_header_buffer_size    1k;
    large_client_header_buffers  4 16k;

    # Gzip sıkıştırma
    gzip  on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json
               application/javascript application/xml+rss
               application/atom+xml image/svg+xml;

    # conf.d altındaki tüm .conf dosyalarını dahil et
    include /etc/nginx/conf.d/*.conf;
}
```

```bash
# Konfigürasyonu doğrula
sudo nginx -t

# Uygula
sudo systemctl reload nginx
```

---

## 7. Sanal Sunucu (Server Block) Oluşturma

```bash
sudo nano /etc/nginx/conf.d/example.com.conf
```

```nginx
server {
    listen 80;
    listen [::]:80;

    server_name example.com www.example.com;

    # Web kök dizini
    root /var/www/example.com/html;
    index index.html index.htm;

    # Charset
    charset utf-8;

    # Erişim logları (site bazında)
    access_log /var/log/nginx/example.com.access.log main;
    error_log  /var/log/nginx/example.com.error.log warn;

    location / {
        try_files $uri $uri/ =404;
    }

    # PHP-FPM (gerekiyorsa)
    # location ~ \.php$ {
    #     fastcgi_pass unix:/run/php/php8.3-fpm.sock;
    #     fastcgi_index index.php;
    #     include fastcgi_params;
    #     fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    # }

    # Statik dosyalar için önbellekleme
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Gizli dosyalara erişimi engelle
    location ~ /\. {
        deny all;
        return 404;
    }
}
```

```bash
# Web dizini oluştur
sudo mkdir -p /var/www/example.com/html
sudo chown -R nginx:nginx /var/www/example.com
sudo chmod -R 755 /var/www/example.com

# Test sayfası
echo "<h1>Nginx 1.29.4 Çalışıyor!</h1>" \
    | sudo tee /var/www/example.com/html/index.html

# Doğrula ve uygula
sudo nginx -t && sudo systemctl reload nginx
```

---

## 8. SSL/TLS Yapılandırması

### Certbot ile Let's Encrypt

```bash
# Certbot kur
sudo apt install certbot python3-certbot-nginx -y

# Sertifika al
sudo certbot --nginx -d example.com -d www.example.com

# Otomatik yenileme testi
sudo certbot renew --dry-run
```

### Manuel SSL Yapılandırması

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    # HTTP'yi HTTPS'ye yönlendir
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;

    server_name example.com www.example.com;

    # SSL sertifikaları
    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # Modern SSL ayarları (TLS 1.2+ zorunlu)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:
                ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:
                ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers off;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/letsencrypt/live/example.com/chain.pem;

    # SSL oturum önbelleği
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # DH parametresi (oluşturmak için: openssl dhparam -out /etc/nginx/dhparam.pem 2048)
    ssl_dhparam /etc/nginx/dhparam.pem;

    root /var/www/example.com/html;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

---

## 9. Güvenlik Sertleştirme

```bash
sudo nano /etc/nginx/conf.d/security-headers.conf
```

```nginx
# Tüm sunuculara uygulanacak güvenlik başlıkları
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

# Nginx versiyonunu gizle (nginx.conf'ta server_tokens off ile birlikte)
more_clear_headers Server;
```

```bash
sudo nano /etc/nginx/conf.d/rate-limit.conf
```

```nginx
# Rate limiting zone tanımları (http bloğu seviyesinde)
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

# Kullanım (server bloğu içinde):
# limit_req zone=api burst=20 nodelay;
# limit_conn conn_limit 10;
```

---

## 10. Performans Ayarları

```bash
# Sistem dosya tanımlayıcı limitini artır
sudo nano /etc/security/limits.conf
```

```
nginx soft nofile 65535
nginx hard nofile 65535
```

```bash
# Kernel parametreleri
sudo nano /etc/sysctl.d/99-nginx.conf
```

```ini
# TCP bağlantı optimizasyonu
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15

# Buffer boyutları
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
```

```bash
sudo sysctl -p /etc/sysctl.d/99-nginx.conf
```

---

## 11. Log Yönetimi

### Logrotate Yapılandırması

```bash
# Varsayılan logrotate config (otomatik gelir)
cat /etc/logrotate.d/nginx
```

```
/var/log/nginx/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 640 nginx adm
    sharedscripts
    postrotate
        if [ -f /run/nginx.pid ]; then
            kill -USR1 `cat /run/nginx.pid`
        fi
    endscript
}
```

### Gerçek Zamanlı Log İzleme

```bash
# Tüm loglar
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log

# Sadece hatalar
sudo tail -f /var/log/nginx/error.log | grep "\[error\]"

# Belirli IP'yi filtrele
sudo tail -f /var/log/nginx/access.log | grep "1.2.3.4"

# HTTP durum koduna göre filtrele (5xx hatalar)
sudo tail -f /var/log/nginx/access.log | awk '$9 ~ /^5/'
```

---

## 12. Güncelleme ve Kaldırma

```bash
# Sürüm sabitlemesini kaldır (güncelleme için)
sudo apt-mark unhold nginx nginx-common

# Mevcut sürüme güncelle
sudo apt update && sudo apt upgrade nginx -y

# Belirli bir sürüme geç
sudo apt install nginx=1.29.X-1~noble -y

# Tekrar sabitle
sudo apt-mark hold nginx nginx-common

# --- Kaldırma ---

# Yapılandırmayı koruyarak kaldır
sudo apt remove nginx nginx-common -y

# Yapılandırma dahil tamamen kaldır
sudo apt purge nginx nginx-common -y
sudo apt autoremove -y

# Depoyu da kaldır
sudo rm /etc/apt/sources.list.d/nginx.list
sudo rm /usr/share/keyrings/nginx-archive-keyring.gpg
sudo rm /etc/apt/preferences.d/99nginx
```

---

## 13. Sık Kullanılan Komutlar

| Komut | Açıklama |
|-------|----------|
| `nginx -v` | Sürüm bilgisi |
| `nginx -V` | Derleme parametreleri |
| `nginx -t` | Konfigürasyon testi |
| `nginx -T` | Konfigürasyonu ekrana bas |
| `nginx -s reload` | Graceful reload |
| `nginx -s stop` | Hızlı durdur |
| `nginx -s quit` | Graceful durdur |
| `nginx -s reopen` | Log dosyalarını yeniden aç |
| `systemctl status nginx` | Servis durumu |
| `systemctl reload nginx` | Systemd üzerinden reload |

---

## 14. Sorun Giderme

### Konfigürasyon Hatası

```bash
sudo nginx -t
# nginx: configuration file /etc/nginx/nginx.conf test failed
# Hata satırını bulup düzelt

sudo nginx -T 2>&1 | grep -n "error"
```

### Port Çakışması

```bash
# 80/443 portunu kim kullanıyor?
sudo ss -tlnp | grep -E ':80|:443'
sudo lsof -i :80
```

### İzin Hatası (403 Forbidden)

```bash
# Dosya izinlerini kontrol et
ls -la /var/www/example.com/html/
sudo chown -R nginx:nginx /var/www/example.com
sudo chmod -R 755 /var/www/example.com
```

### Servis Başlamıyor

```bash
# Detaylı hata logu
sudo journalctl -u nginx -n 50 --no-pager
sudo tail -20 /var/log/nginx/error.log

# PID dosyası çakışması
sudo rm -f /run/nginx.pid
sudo systemctl start nginx
```

### SSL Sertifika Hatası

```bash
# Sertifika geçerliliğini kontrol et
sudo openssl x509 -in /etc/letsencrypt/live/example.com/fullchain.pem \
    -noout -dates

# SSL bağlantısını test et
openssl s_client -connect example.com:443 -servername example.com

# Certbot yenileme
sudo certbot renew --force-renewal
```

---

## Referanslar

- [Nginx Resmi Belgeleri](https://nginx.org/en/docs/)
- [Nginx Mainline Deposu](https://nginx.org/en/linux_packages.html#Ubuntu)
- [Mozilla SSL Konfigürasyon Üreticisi](https://ssl-config.mozilla.org/)
- [Nginx Güvenlik Tavsiyeleri](https://nginx.org/en/security_advisories.html)
