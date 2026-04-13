### 4. Fail2Ban Kurulumu ve Özel Jail Tanımlanması

# Engelleme mekanizması için işletim sistemine `fail2ban` kurun:

sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

Bu repo dizinindeki (veya kendi belirlediğiniz) Fail2Ban konfigürasyon dosyalarını `/etc/fail2ban/` klasörüne kopyalayarak OpenAppSec loglarını dinlemesini sağlayın:

git clone https://github.com/KULLANICI_ADINIZ/nginx-nginxui-waf-fail2ban-stack.git
cd nginx-nginxui-waf-fail2ban-stack

sudo cp fail2ban/jail.local /etc/fail2ban/jail.local
sudo cp fail2ban/filter.d/openappsec.conf /etc/fail2ban/filter.d/

# Kuralların aktif olması için servisi yeniden başlatın
sudo systemctl restart fail2ban

## ⚙️ Yapılandırma Detayları

### Fail2Ban Jail ve Filtre Ayarları
Fail2Ban, OpenAppSec/Nginx hata loglarını analiz edecek şekilde tasarlanmıştır. `jail.local` içerisindeki kurallarınıza göre;
- `findtime = 600` (Ayarlanan zaman dilimi, örneğin: 10 dk)
- `maxretry = 3` (3 hatalı/zararlı tespitin eşik noktası)
- `bantime = 3600` (IP'nin sistemden dışlanacağı ve iptables ile tamamen yasaklanacağı süre: 1 Saat)
