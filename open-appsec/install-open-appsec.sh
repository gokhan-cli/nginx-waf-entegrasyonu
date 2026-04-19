## 3. OpenAppSec Kurulumu ve WAF Entegrasyonu

# OpenAppSec merkezi bulut (SaaS) yerine tamamen **yerel (local)** olarak yönetilecek ve çalışacaktır. 
# Bu nedenle kurulum, offline entegrasyonu sağlamak adına "download mod" ile ilerleyecektir:

wget https://downloads.openappsec.io/open-appsec-install && chmod +x open-appsec-install 

# OpenAppSec'i yerel yönetim için download modunda çalıştıran komut:
sudo ./open-appsec-install --download # OpenAppSec localde çalışağı için biz bu modu kullanacağız.

#Eğer yukarıdaki script ile kurulumda sorun yaşarsanız, klasör içindeki dosyayı sunucunuza çekip kullanabilirsiniz.
wget https://raw.githubusercontent.com/gokhan-cli/nginx-nginxui-waf-fail2ban-stack/refs/heads/main/open-appsec/open-appsec-install && chmod +x open-appsec-install

# Yine kurulum için aşağıdaki parametreleri kullanacağız.
sudo ./open-appsec-install --download

# Sonrasında aşağıdaki kütüphaneleri library dizinine kopyalıyoruz.
cp /tmp/open-appsec/ngx_module_1.29.8-1-noble/libshmem_ipc_2.so /usr/lib
cp /tmp/open-appsec/ngx_module_1.29.8-1-noble/libosrc_shmem_ipc.so /usr/lib
cp /tmp/open-appsec/ngx_module_1.29.8-1-noble/libosrc_compression_utils.so /usr/lib
cp /tmp/open-appsec/ngx_module_1.29.8-1-noble/libosrc_nginx_attachment_util.so /usr/lib

# Nginx Attacment dosyasını da nginx modül dizinine kopyalıyoruz.
cp /tmp/open-appsec/ngx_module_1.29.8-1-noble/ngx_cp_attachment_module.so /usr/lib/nginx/modules/ngx_cp_attachment_module.so

# Modülü nginx üzerinde aktif etmek için aşağıdaki komutu yazıp nginx.conf dosyamızın en üstüne ekliyoruz.
sudo sed -i '1s|^|load_module /usr/lib/nginx/modules/ngx_cp_attachment_module.so;\n|' /etc/nginx/nginx.conf
sudo systemctl restart nginx
# Hata almadıysak işlem başarılı olmuş demektir.
# Son olarak aşağıdakileri de çalıştırıyoruz.
/tmp/open-appsec/openappsec/install-cp-nano-agent.sh --install --hybrid_mode --server 'NGINX Server'
nano /etc/cp/conf/local_policy.yaml
# Policy mode detect-learn yerine prevent-learn olacak.
open-appsec-ctl -ap
/tmp/open-appsec/openappsec/./install-cp-nano-agent-cache.sh --install
/tmp/open-appsec/openappsec/install-cp-nano-service-http-transaction-handler.sh --install
/tmp/open-appsec/openappsec/install-cp-nano-attachment-registration-manager.sh --install

