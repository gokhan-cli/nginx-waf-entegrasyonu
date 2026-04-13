## 3. OpenAppSec Kurulumu ve WAF Entegrasyonu

OpenAppSec merkezi bulut (SaaS) yerine tamamen **yerel (local)** olarak yönetilecek ve çalışacaktır. Bu nedenle kurulum, offline entegrasyonu sağlamak adına "download mod" ile ilerleyecektir:

```bash
wget https://downloads.openappsec.io/openappsec-install
chmod +x openappsec-install

# OpenAppSec'i yerel yönetim için download modunda çalıştıran komut:
sudo ./openappsec-install --download

# (İndirilen paketi sisteminize göre genişleterek kurulum dosyasından
# yerel yönetim (Local Management / Declarative) seçeneğiyle entegrasyonu tamamlayın.)
```

# *(Not: Kurulum download modunda ve tamamen "local" yapıldığından, WAF konfigürasyonunuz ve tespit kurallarınız sunucunuz üzerindeki yerel politika dosyası (`local_policy.yaml`) aracılığıyla yönetilecektir. Entegrasyon tamamlandığında eklenti `nginx.conf` içerisine gömülecektir.)*
