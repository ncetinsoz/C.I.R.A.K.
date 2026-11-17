<div align="center">

<img src="assets/images/cirak_logo.png" alt="Ç.I.R.A.K. Logo" width="300" />

# Ç.I.R.A.K.
### Çok Amaçlı İnceleme, Raporlama ve Ağ Keşif Cihazı
**Multi-Purpose Inspection, Reporting, and Network Discovery Instrument**

[Türkçe](#türkçe) | [English](#english)

</div>

---

<a name="türkçe"></a>
## Türkçe

### Proje Kapsamı ve Amacı
**Ç.I.R.A.K.** (*Çok Amaçlı İnceleme, Raporlama ve Ağ Keşif Cihazı*), Yönetim Bilişim Sistemleri (YBS) Yüksek Lisans Tezi kapsamında geliştirilen taşınabilir bir saha ağ analiz ve arıza tespit el terminalidir.

Kurumsal ve kampüs bilgi teknolojileri altyapılarında yaşanan ağ kesintileri, hatalı VLAN veya port yapılandırmaları, IP çakışmaları ve ağa izinsiz dahil edilen yetkisiz (sahte) DHCP sunucuları iş sürekliliğini doğrudan tehdit etmektedir. Bu çalışma; merkezde proaktif gözlem ve karar destek sağlayan **K.A.L.F.A.** (*Kampüs Ağları Lojistik Faaliyet Asistanı*) ile sahada hızlı teşhis ve doğrulama sağlayan **Ç.I.R.A.K.** el terminalinden oluşan bütünleşik mimarinin saha katmanını oluşturmaktadır.

Cihazın temel amacı, teknik servis ekiplerinin arıza bildirilen uç noktada harici bir bilgisayara ihtiyaç duymadan saniyeler içinde çok katmanlı ağ analizi yapabilmesini ve ortalama arıza çözüm süresini (MTTR) en aza indirmesini sağlamaktır.

### Sahada Yetkisiz DHCP ve Port Tespiti
Yerel ağlarda kullanıcıların bilinçsizce veya yetkisiz biçimde ağa dahil ettiği modem ve yönlendiriciler, istemcilere hatalı IP adresleri dağıtarak ağ trafiğini kesintiye uğratmaktadır. Ç.I.R.A.K., fiziksel hat arasına ek bir donanım takılmasına gerek duymadan tek bir ağ portu üzerinden şu işlemleri yürütür:
1. Bulunduğu yerel ağdaki yetkisiz DHCP sunucu yayınlarını tespit eder ve kurumsal beyaz liste ile karşılaştırır.
2. Tespit edilen sahte cihazın donanım (MAC) adresini ağ anahtarları (switch) üzerinden sorgulayarak, cihazın hangi anahtara ve hangi fiziksel porta bağlı olduğunu ekranda raporlar.
3. Müdahale sonrasında hattın normale döndüğünü doğrulayarak merkezi karar destek sistemine bildirim sunar.

### Temel Saha Yetenekleri
* **Otomatik Test:** Ağ kablosu takıldığında 10 saniye içinde fiziksel bağlantı, anahtar/VLAN bilgisi, DHCP adres alımı, ağ geçidi erişimi, DNS çözümleme ve dış ağ bağlantısını sırasıyla doğrular.
* **Anahtar, Port ve VLAN Keşfi:** Ağ paketlerini dinleyerek kablonun bağlı olduğu anahtarın adını, modelini, IP adresini, port numarasını ve VLAN kimliğini çözer.
* **Port Işıkları (Fiziksel Port Gösterimi):** Bağlı olunan anahtar portunun durum ışığını kontrollü biçimde yakıp söndürerek sistem kabinindeki etiketsiz kabloların gözle tespit edilmesini sağlar.
* **Alt Ağ Keşfi ve IP Doluluk Raporu:** Bulunulan alt ağdaki dolu ve boş IP oranlarını, olası IP çakışmalarını ve bağlı cihazların üretici dağılımlarını listeler.
* **Bant Genişliği ve Hız Testi:** Yerel sunucuya ve dış ağa gerçek veri yükü göndererek hattın veri aktarım hızını, gecikme süresini ve paket kaybı oranını ölçer.
* **Kablosuz Ağ Analizi:** Dahili kablosuz ağ birimi aracılığıyla çevredeki yayın adlarını (SSID), erişim noktası adreslerini, sinyal güçlerini ve kanal çakışmalarını inceler.

### Donanım ve Yazılım Mimarisi
Cihaz, sahada kararlı ve düşük kaynak tüketimiyle çalışacak şekilde yerel (native) bir mimari üzerine inşa edilmiştir:
* **Donanım Birimi:** Raspberry Pi 4 Model B ve resmi 7 inç kapasitif dokunmatik ekran (800x480 çözünürlük, DSI görüntü veri yolu).
* **Yazılım Altyapısı:** Linux (Raspberry Pi OS Lite) işletim sistemi üzerinde çalışan Python 3 ve PySide6 (Qt6) grafik arayüz çatısı. Masaüstü pencere yöneticisine ihtiyaç duymadan doğrudan ekran çerçeve belleği üzerinden hızlı açılış ve kesintisiz çalışma sağlar.


---

<a name="english"></a>
## English

### Project Scope and Purpose
**Ç.I.R.A.K.** (*Multi-Purpose Inspection, Reporting, and Network Discovery Instrument*) is a portable field network analysis and troubleshooting handheld terminal developed as part of a Master's Thesis in Management Information Systems (MIS).

Network outages, misconfigured VLANs or switch ports, IP address conflicts, and unauthorized (rogue) DHCP servers introduced into corporate and campus IT infrastructures directly threaten business continuity. This study constitutes the field layer of an integrated two-tier architecture consisting of **K.A.L.F.A.** (*Campus Networks Logistic Activity Assistant*), which provides proactive monitoring and decision support at the center, and the **Ç.I.R.A.K.** handheld terminal, which provides rapid diagnostics and verification in the field.

The primary objective of the device is to enable technical service teams to perform multi-layer network diagnostics within seconds at the reported fault location without requiring an external computer, thereby minimizing Mean Time to Repair (MTTR).

### Field Rogue DHCP and Port Localization
Modems and routers inadvertently or illicitly connected to local area networks distribute invalid IP configurations to clients and disrupt network traffic. Without requiring an inline hardware tap, Ç.I.R.A.K. performs the following operations over a single network port:
1. Detects unauthorized DHCP server broadcasts within the local network and compares them against the corporate whitelist.
2. Queries network switches using the hardware (MAC) address of the detected rogue device to identify and display the exact switch and physical port to which the offending device is connected.
3. Verifies that the network line has returned to normal operation following remediation and reports the result to the central decision support system.

### Core Field Capabilities
* **Automated Test (AutoTest):** Within 10 seconds of connecting a network cable, sequentially verifies physical link status, switch/VLAN identity, DHCP address allocation, default gateway reachability, DNS resolution, and external network connectivity.
* **Switch, Port, and VLAN Discovery:** Passively listens to network discovery frames to resolve the connected switch name, model, IP address, port number, and VLAN ID.
* **Port Blink (Physical Port Identification):** Repeatedly toggles the status indicator LED of the connected switch port to allow visual identification of unlabeled cables inside wiring closets.
* **Subnet Discovery and IP Utilization Report:** Lists active and available IP ratios within the current subnet, identifies potential IP conflicts, and classifies connected devices by hardware manufacturer.
* **Bandwidth and Speed Test:** Measures actual data throughput, latency, and packet loss by generating traffic toward a local server and external network targets.
* **Wireless Network Analysis:** Utilizes the onboard wireless interface to inspect nearby network names (SSIDs), access point addresses, signal strength levels, and channel overlaps.

### Hardware and Software Architecture
The instrument is built upon a native software stack designed for high stability and minimal resource consumption in field conditions:
* **Hardware Unit:** Raspberry Pi 4 Model B paired with the official 7-inch capacitive touchscreen display (800x480 resolution, DSI display interface).
* **Software Stack:** Python 3 and PySide6 (Qt6) graphical user interface framework running on Linux (Raspberry Pi OS Lite). Operates directly over the system framebuffer without requiring a desktop window manager, ensuring rapid boot times and reliable performance.

### Installation and Execution

```bash
# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run application in development environment
python -m cirak.app

# Run directly on the device display via framebuffer
QT_QPA_PLATFORM=eglfs python -m cirak.app
```

---

## Lisans / License
Bu proje, Yönetim Bilişim Sistemleri Yüksek Lisans Tezi araştırması kapsamında geliştirilmektedir.  
This project is developed as part of a Master's Thesis research in Management Information Systems.
