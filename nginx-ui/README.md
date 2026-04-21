# Nginx UI Kurulum Rehberi (Ubuntu 24.04)

`Nginx UI`, Nginx yapılandırmalarınızı, SSL sertifikalarınızı ve metriklerinizi şık ve modern bir web arayüzü üzerinden yönetmenizi sağlayan güçlü bir yönetim panelidir. Nginx Proxy Manager'dan farklı olarak, doğrudan sisteminizdeki mevcut Nginx servisini ve `/etc/nginx` yapılandırma dosyalarınızı (mevcut yapıyı bozmadan) okuyup yönetir.

Bu kurulum, Ubuntu 24.04 üzerinde en pratik yöntem olan **Kurulum Betiği (Install Script)** ile yapılmasını anlatır.

---

## 1. Nginx UI Kurulumu

Nginx UI'ı kurmak sadece tek bir komutla mümkündür. Sisteminize root olarak (veya `sudo` ile) girin ve aşağıdaki resmi kurulum betiğini çalıştırın:

```bash
bash <(curl -L -s https://raw.githubusercontent.com/0xJacky/nginx-ui/master/install.sh) install
```

Bu komut:
- Nginx UI sistem dosyalarını `/usr/local/etc/nginx-ui` dizinine yerleştirir.
- Bir `nginx-ui` systemd servisi oluşturur ve otomatik başlangıca ekler.
- Arayüzü varsayılan olarak **9000** portundan ayağa kaldırır.

*(İpucu: Güncelleme yapmak istediğinizde sadece sondaki `install` yerine `update` yazıp aynı komutu çalıştırırsınız).*

## 2. Kurulum Sonrası Kontrol

Kurulum tamamlandıktan sonra servisin çalışıp çalışmadığını kontrol edin:

```bash
sudo systemctl status nginx-ui
```
*(Yemyeşil bir `active (running)` ibaresi görmelisiniz).*

Eğer Nginx UI panelinizi dış dünyaya açmak yerine bir Reverse Proxy (Yine Nginx'in kendisi) arkasına almak isterseniz veya portunu değiştirmek isterseniz ayar dosyası şuradadır:
```bash
sudo nano /usr/local/etc/nginx-ui/app.ini
```

## 3. Web Arayüzüne İlk Giriş ve Ayarlar

Her şey sorunsuz çalışıyorsa, tarayıcınızı açın ve sunucunuzun IP adresi ile 9000 portuna gidin:
**`http://SUNUCU_IP:9000`**

### İlk Kurulum Sihirbazı (Setup Wizard)
Arayüze ilk girdiğinizde karşınıza bir kurulum sihirbazı çıkacak:
1. **Database Set up:** Varsayılan değer olarak `SQLite` seçili gelir, aynen devam edin. (Gelişmiş kullanıcılar MySQL'e de bağlayabilir ancak SQLite bu panel için her zaman daha güvenli ve hızlıdır).
2. **Admin Account:** Buraya Nginx UI panelini yöneteceğiniz Kullanıcı Adı, Şifre ve Email bilgilerinizi girin.
3. **Nginx Ayarları:**
   - Sihirbaz sizden Nginx'in yapılandırma dizinini isteyecek (Oraya: `/etc/nginx` yazın).
   - Nginx log dizinini isteyecek (Oraya: `/var/log/nginx` yazın).
   - Eğer açık değilse Nginx UI panelinden Nginx servisini Yeniden Başlatma/Durdurma yetkilerini verin.

## 4. Kullanım İpuçları
* **WebShell (Terminal):** Tarayıcı üzerinden dâhili Web Terminali ile doğrudan sunucu shell ortamına erişebilirsiniz.
* **Görsel Konfigürasyon:** Sağ bloktaki menülerden `Server Blocks` (Sanal Sunucular) oluşturabilir ve open-appsec politikalarınızı yönetebilirsiniz.
* *(Eğer Cloudflare veya Let's Encrypt SSL kullanacaksanız DNS Auto-Renew gibi özellikleri ayarlar sekmesinden entegre edebilirsiniz).*

> [!WARNING]
> Nginx UI'nin kullandığı **9000** portu dış dünyaya ve dış IP'ye herkese açık olacaktır. Güvenliğiniz için Ubuntu güvenlik duvarından (UFW) bu porta sadece kendi sabit İnternet (Ev/Ofis) IP numaranızın girişine izin verebilirsiniz:
> `sudo ufw allow from <SİZİN_KİŞİSEL_İP_ADRESİNİZ> to any port 9000`
