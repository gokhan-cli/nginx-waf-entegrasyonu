## 3. OpenAppSec Kurulumu ve WAF Entegrasyonu

# OpenAppSec merkezi bulut (SaaS) yerine tamamen **yerel (local)** olarak yönetilecek ve çalışacaktır. 
# Bu nedenle kurulum, offline entegrasyonu sağlamak adına "download mod" ile ilerleyecektir:

wget https://downloads.openappsec.io/open-appsec-install && chmod +x open-appsec-install 

# OpenAppSec'i yerel yönetim için download modunda çalıştıran komut:
sudo ./open-appsec-install --auto # Download modda kurulum aşamasında hata almamak için kurulumu önce bu modda çalıştırın.
sudo ./open-appsec-install --download # OpenAppSec yerelde çalışağı için biz bu modu kullanacağız.

#Eğer yukarıdaki script ile kurulumda sorun yaşarsanız buradaki dosyayı open-appsec-install kullanabilirsiniz.
