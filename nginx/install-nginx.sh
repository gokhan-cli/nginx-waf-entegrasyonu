### 1. Nginx ve Gerekli Bileşenlerin Kurulumu

# İşletim sisteminize uygun Nginx sürümünü kurun ve kurulan sürümü kontrol edin:

sudo apt update
sudo apt install nginx=1.29.4-1~noble curl wget unzip -y

# WAF uyumluluğunun bozulmaması için Nginx sürümünü sabitliyoruz (hold):
sudo apt-mark hold nginx

nginx -v # Çıkan sürüm: nginx version: nginx/1.29.4

sudo systemctl enable nginx
sudo systemctl start nginx
