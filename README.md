# Ç.I.R.A.K. (Çok Amaçlı İnceleme, Raporlama ve Ağ Keşif Cihazı)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![GUI](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-brightgreen)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%20OS%20Lite%20%2F%20Linux-orange)
![Display](https://img.shields.io/badge/Display-7%22%20Touch%20800x480-purple)

**Ç.I.R.A.K.** (*Çok Amaçlı İnceleme, Raporlama ve Ağ Keşif Cihazı*), Yönetim Bilişim Sistemleri (YBS) Yüksek Lisans Tezi kapsamında geliştirilmekte olan açık kaynaklı, taşınabilir ve endüstriyel standartlarda bir el terminali ağ analiz cihazıdır. 

Bu tür ticari cihazların endüstriyel kararlılığını modern dokunmatik ergonomisiyle harmanlayan Ç.I.R.A.K., sistem ve ağ yöneticilerine sahada saniyeler içinde L1-L7 katmanlarında tam teşhis, sahte DHCP tespiti ve ağ haritalama imkanı sunar.

---

## 🎯 Temel Özellikler

1. **⚡ Otomatik Test (AutoTest L1 - L7):** 
   - 10 saniyede fiziksel link (hız, dubleks, MDIX), LLDP/CDP anahtar/port/VLAN, DHCP IP kiralama, varsayılan ağ geçidi ping & ARP MAC, kampüs içi DNS sorgusu ve ULAKBİM/dış ağ HTTP 200 OK doğrulamasını otomatik gerçekleştirir.
2. **🔍 Ağ Keşfi & Teşhis Araçları:**
   - **LLDP / CDP Paket Dinleyicisi:** Switch adı, port kimliği, VLAN ve yönetim IP'sini anında yakalar.
   - **Port Işıkları (Flaşör):** Switch port LED'ini periyodik yakıp söndürerek kabinet kablolama takibini kolaylaştırır (`ethtool --identify`).
   - **Alt Ağ IP Doluluk (Hızlı ARP Sweep):** /24 ağındaki aktif cihazları ve MAC adreslerini saniyeler içinde listeler.
3. **🚨 Yetkisiz DHCP (Rogue DHCP Hunter):**
   - Kurumsal ağda açılan yetkisiz modemleri, sahte yönlendiricileri ve DHCP sunucularını anında yakalar; yetkili sunucu beyaz listesi ile karşılaştırarak alarm üretir.
4. **🚀 Hız Testi (iPerf3):**
   - Ağ geçidi veya yerel iPerf3 sunucusuna throughput, gecikme ve jitter ölçümü yapar.
5. **📶 Kablosuz Ağ (Wi-Fi Keşfi):**
   - Kampüs SSID'lerini, sinyal kalitesini (RSSI) ve kanal yoğunluğunu listeler.
6. **⚙️ Çift Tema & Ergonomik Dokunmatik Arayüz:**
   - 7 inç 800×480 dokunmatik ekran için optimize edilmiş 240×160 px butonlar.
   - **Karanlık Mod (Dark Industrial - #020617)** ve **Aydınlık Mod (Light Industrial - #f8fafc)** destekli Qt/QSS tema motoru.

---

## 🛠 Donanım & Sistem Mimarisi

* **Ana İşlemci Birimi:** Raspberry Pi 4 Model B (Broadcom BCM2711, Quad-core Cortex-A72 @ 1.5GHz)
* **İşletim Sistemi:** Raspberry Pi OS Lite (Debian Bookworm tabanlı)
* **Ekran:** Resmi Raspberry Pi 7" Kapasitif Dokunmatik Ekran (800×480 @ 60Hz, MIPI DSI)
* **Fiziksel Ağ Portu:** 10/100/1000 Gigabit Ethernet (eth0 - Broadcom BCM54213PE PHY)
* **Kablosuz Ağ:** Onboard 2.4/5.0 GHz IEEE 802.11ac Wi-Fi
* **Güç & Batarya:** 5.1V / 3A USB-C PD veya batarya yönetim şapkası

---

## 📐 Yazılım & Modül Yapısı

```
cirak/
├── app.py                   # PySide6 uygulama giriş noktası
├── config.py                # Ekran çözünürlüğü, renkler, zaman aşımları ve profiller
├── core/                    # Temel veri modelleri ve asenkron sinyal yapısı
│   ├── models.py            # TestResult, NetworkStatus, DHCPInfo, LLDPInfo veri sınıfları
│   ├── signals.py           # Qt Signal/Slot yöneticisi
│   └── worker.py            # QRunnable / QThreadPool arka plan iş parçacığı yöneticisi
├── backend/                 # Ağ teşhis motoru ve test fonksiyonları
│   ├── base.py              # TestBase soyut taban sınıfı
│   ├── physical_link.py     # L1: Link hızı, dubleks, carrier ve sayaçlar
│   ├── lldp_cdp.py          # L2: LLDP ve CDP paket yakalama & ayrıştırma
│   ├── dhcp.py              # L3: DHCP işlem zamanı, lease ve Rogue DHCP tespiti
│   ├── ping.py              # L3: Ağ geçidi ping ve ARP MAC çözümleme
│   ├── dns_test.py          # L7: DNS çözümleme gecikmesi ve sunucu testi
│   ├── external_test.py     # L7: ULAKBİM / Web erişilebilirlik ve HTTP 200 doğrulaması
│   ├── autotest.py          # L1-L7 tam zincir orkestratörü
│   ├── port_blinker.py      # Switch port LED flaşörü (ethtool blink)
│   ├── arp_scanner.py       # Alt ağ hızlı ARP tarayıcısı
│   ├── iperf_runner.py      # iPerf3 throughput / jitter istemcisi
│   └── wifi_scanner.py      # Kablosuz ağ arayüzü taraması
└── gui/                     # 800x480 dokunmatik arayüz bileşenleri
    ├── theme.py             # Aydınlık / Karanlık QSS tema paleti
    ├── main_window.py       # Sabit 800x480 ana pencere ve sayfa yönlendiricisi
    ├── components/          # Üst durum çubuğu, alt bilgi çubuğu, dokunmatik butonlar
    └── views/               # Ana menü, AutoTest, Keşif, Rogue DHCP ve Açılış ekranları
```

---

## 🚀 Kurulum ve Çalıştırma

### Bağımlılıkların Yüklenmesi
```bash
# Python sanal ortamı oluşturma
python3 -m venv .venv
source .venv/bin/activate

# Paketleri yükleme
pip install -r requirements.txt
```

### Testleri Çalıştırma
```bash
pytest -v
```

### Arayüzü Başlatma
```bash
# Geliştirme ortamında çalıştırma
python -m cirak.app

# Raspberry Pi üzerinde EGLFS / Linux DRM ile çalıştırma (X11 olmadan)
QT_QPA_PLATFORM=eglfs python -m cirak.app
```

---

## 📄 Lisans
Bu proje YBS Yüksek Lisans Tezi araştırması kapsamında geliştirilmektedir. Tüm hakları saklıdır.
