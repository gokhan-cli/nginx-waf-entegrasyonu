# CrowdSec Kurulum Rehberi (Ubuntu 24.04)

Bu rehber, projenin arka planında Ubuntu tarafında yapmanız gereken ayarlamaları açıklar. open-appsec'in gönderdiği JSON formatındaki logları CrowdSec'e okutacağız.

## 1. CrowdSec ve Bouncer Kurulumu

Henüz kurulu değilse CrowdSec ve Bouncer'ı Ubuntu makinenize kurun:
```bash
curl -s https://packagecloud.io/install/repositories/crowdsec/crowdsec/script.deb.sh | sudo bash
sudo apt install crowdsec -y

# Ağ (iptables/nftables) seviyesinde yasaklamak için:
sudo apt install crowdsec-firewall-bouncer-iptables -y
```

## 2. open-appsec Loglarını Dinleme (Acquisition)

CrowdSec'e open-appsec'in loglarını nerede bulacağını söylememiz gerekiyor. Güncel CrowdSec sürümlerinde bu ayarlar `acquis.d` klasörü altında ayrı dosyalar olarak tutulur.

Yeni bir dosya oluşturun: `sudo nano /etc/crowdsec/acquis.d/open-appsec.yaml`
İçerisine şu satırları ekleyin:
```yaml
filenames:
  - /var/log/nano_agent/cp-nano-http-transaction-handler.log*
labels:
  type: open-appsec
```

## 3. JSON Log Parser (Ayrıştırıcı) Oluşturma

Loglar düz metin değil JSON. İçinden `sourceIP` ve `securityAction` değerlerini ayıklamak için özel bir parser yazıyoruz.

`sudo nano /etc/crowdsec/parsers/s01-parse/open-appsec.yaml` dosyasını oluşturun ve içine şunu yapıştırın:
```yaml
filter: "evt.Parsed.program == 'open-appsec'"
onsuccess: next_stage
name: custom/open-appsec-parser
description: "Parse open-appsec JSON transaction logs"
nodes:
  - filter: "evt.Line.Raw contains 'eventData'"
    statics:
      - parsed: "json_unmarshaled"
        expression: "UnmarshalJSON(evt.Line.Raw, evt.Unmarshaled, 'appsec')"
      - meta: "source_ip"
        expression: "evt.Unmarshaled.appsec.eventData.sourceIP"
      - meta: "action"
        expression: "evt.Unmarshaled.appsec.eventData.securityAction"
      - meta: "http_path"
        expression: "evt.Unmarshaled.appsec.eventData.httpUriPath"
```

## 4. Senaryo Oluşturma

open-appsec'ten "Prevent" (Engelle) etiketi yemiş bir isteği anında CrowdSec'te de banlatacak senaryo.

`sudo nano /etc/crowdsec/scenarios/open-appsec-block.yaml` dosyasını oluşturun:
```yaml
type: leaky
name: custom/open-appsec-prevent
description: "If open-appsec blocked a request, ban it in CrowdSec"
filter: "evt.Meta.action == 'Prevent'"
groupby: "evt.Meta.source_ip"
capacity: 1        # 1 kere bile gerçekleşse
leakspeed: "10m"   # anında banla
blackhole: 1m
labels:
  service: open-appsec
  type: wapp
  remediation: true
```

## 5. Sistemi Yeniden Yükleme ve Test

CrowdSec'i yeniden başlatın ve parser/senaryonun düzgün yüklendiğini kontrol edin:
```bash
sudo systemctl restart crowdsec
sudo cscli parsers list
sudo cscli scenarios list
```

Test etmek için dışarıdan open-appsec'e bir XSS veya SQLi atın. `tail -f /var/log/crowdsec/crowdsec.log` dosyasında `custom/open-appsec-prevent` tetiklenmiş mi diye görebilirsiniz. `sudo cscli decisions list` yazınca da göreceksiniz.

## 6. Web Yönetim Paneli İçin Sudoers Ayarı

Geliştirdiğim şık yönetim panelini (`app.py`) çalıştıracak olan kullanıcı (`ubuntu` veya `www-data` kimse) parola sormadan `cscli` komutunu çalıştırabilmelidir, aksi halde web panelinden ban kaldıramaz.

`sudo visudo` yazın ve en alta şu satırı ekleyin (Eğer paneli `ubuntu` kullanıcısı ile çalıştırıyorsanız):
```text
ubuntu ALL=(ALL) NOPASSWD: /usr/bin/cscli decisions list -o json, /usr/bin/cscli decisions delete -i *
```

*(Not: Eğer paneli Flask/Gunicorn arkasında `www-data` ile çalıştıracaksanız `ubuntu` yerine `www-data` yazın).*

## 7. Crowdsec Arayüz Yönetimi İçin Hazırlık

Kodlarını yazdığım yeni projenin bulunduğu klasöre gidin.
```bash
sudo mkdir -p /opt/crowdsec-gui
sudo chown www-data:www-data /opt/crowdsec-gui
```

Sanal ortam ve paketleri kurun.
```bash
cd /opt/crowdsec-gui
sudo -u www-data python3 -m venv venv
sudo -u www-data /opt/crowdsec-gui/venv/bin/pip install flask bcrypt
```

Gunicorn uygulamasını kurun.
```bash
sudo apt install gunicorn
```

Gunicorn için servis tanımlarını yapın.
```bash
nano /etc/systemd/system/crowdsec-gui.service
```

Aşağıdaki kodları crowdsec-gui servisi içine yazıp dosyayı kaydediyorum.
```bash
[Unit]
Description=Crowdsec Gui Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/crowdsec-gui
Environment="PATH=/opt/crowdsec-gui/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Servisi aktif edip çalıştırıyorum.

*Flask içinde port tanımı 5001 olarak tanımlanmıştır. Siz isterseniz bunu değiştirebilirsiniz.*

*app.py içinde 96. satıra gidin.*

*app.run(host='0.0.0.0', port=5001, debug=True)*

*Production ortamı için Flask önerilmez.*

*(Production ortamı için `gunicorn -w 4 -b 0.0.0.0:5000 app:app` 5000 yada istediğiniz bir portu kullanabilirsiniz.)*

Sonra tarayıcınızdan `http://SUNUCU_IP:5000` adresine giderek muazzam arayüzü görebilirsiniz!
```bash
systemctl enable crowdsec-gui
systemctl start crowdsec-gui
```
