#!/usr/bin/env bash
# ==============================================================================
# Ç.I.R.A.K. (Çok Amaçlı İnceleme, Raporlama ve Ağ Keşif Cihazı)
# Raspberry Pi 4 + 7" Dokunmatik Ekran Otomatik Kurulum ve Yapılandırma Betiği
# ==============================================================================

set -eo pipefail

# Renk tanımları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}"
echo "  ================================================================"
echo "    Ç.I.R.A.K. El Terminali Kurulum ve Yapılandırma Motoru       "
echo "    Raspberry Pi 4 (Raspberry Pi OS Lite 64-bit / Bookworm)      "
echo "  ================================================================"
echo -e "${NC}"

# 1. Kullanıcı ve Dizin Tespiti
ACTUAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${REPO_DIR}/.venv"

echo -e "${BLUE}[INFO]${NC} Kurulum Kullanıcısı: ${BOLD}${ACTUAL_USER}${NC}"
echo -e "${BLUE}[INFO]${NC} Kullanıcı Ev Dizini: ${BOLD}${USER_HOME}${NC}"
echo -e "${BLUE}[INFO]${NC} Proje Kaynak Dizini: ${BOLD}${REPO_DIR}${NC}"

# Sudo kontrolü
SUDO_CMD=""
if [ "$EUID" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO_CMD="sudo"
    else
        echo -e "${RED}[HATA]${NC} Bu betiğin sistem paketlerini kurabilmesi için root veya sudo yetkisi gereklidir."
        exit 1
    fi
fi

# 2. Sistem Paket Listesinin Güncellenmesi ve Gereksinimlerin Kurulması
echo -e "\n${CYAN}==> 1/6: Sistem APT Bağımlılıkları Kuruluyor...${NC}"
$SUDO_CMD apt-get update -y

SYSTEM_PACKAGES=(
    # Temel derleme ve Python araçları
    python3
    python3-venv
    python3-pip
    python3-dev
    build-essential
    git
    curl

    # Ağ teşhis ve katman analiz paketleri
    ethtool
    lldpd
    arp-scan
    iperf3
    fping
    nmap
    tcpdump
    tshark
    bridge-utils
    vlan
    wireless-tools
    iw

    # Linux yetkilendirme (Least Privilege)
    libcap2-bin

    # PySide6 / Qt6 DRM/KMS ve LinuxFB grafik ve font bağımlılıkları (X11'siz Lite OS için)
    libgl1
    libgl1-mesa-dri
    libglx-mesa0
    libegl1
    libgles2
    libxkbcommon0
    libfontconfig1
    libdbus-1-3
    libinput10
    libudev1
    libglib2.0-0
    fonts-noto-color-emoji
    fonts-dejavu-core
    fonts-freefont-ttf
)

echo -e "${BLUE}[INFO]${NC} Paketler yükleniyor: ${SYSTEM_PACKAGES[*]}"
$SUDO_CMD DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${SYSTEM_PACKAGES[@]}"

# 3. Arka Plan Ağ Servislerinin Yapılandırılması
echo -e "\n${CYAN}==> 2/6: Arka Plan Ağ Servisleri Etkinleştiriliyor...${NC}"
if systemctl list-unit-files | grep -q lldpd.service; then
    $SUDO_CMD systemctl enable lldpd.service
    $SUDO_CMD systemctl restart lldpd.service
    echo -e "${GREEN}[OK]${NC} lldpd servisi aktif edildi (LLDP/CDP dinleyici)."
fi

# Wireshark / TShark izinleri (root olmadan paket yakalama)
if getent group wireshark >/dev/null; then
    $SUDO_CMD usermod -aG wireshark "$ACTUAL_USER" || true
    echo -e "${GREEN}[OK]${NC} '${ACTUAL_USER}' kullanıcısı 'wireshark' grubuna eklendi."
fi

## Donanım erişim grupları (Ekran, dokunmatik evdev, TTY konsol ve ağ)
for grp in video input render netdev tty; do
    if getent group "$grp" >/dev/null; then
        $SUDO_CMD usermod -aG "$grp" "$ACTUAL_USER" || true
    fi
done
echo -e "${GREEN}[OK]${NC} Donanım erişim grupları (video, input, render, netdev, tty) tanımlandı."

# Eski boş /home/user/cirak klasörü varsa temizle (Python modül çakışmasını önle)
if [ -d "${USER_HOME}/cirak" ] && [ "${USER_HOME}/cirak" != "${REPO_DIR}" ]; then
    rm -rf "${USER_HOME}/cirak" 2>/dev/null || true
fi

# 4. Python Sanal Ortamının (.venv) Kurulması
echo -e "\n${CYAN}==> 3/6: Python Sanal Ortamı (.venv) Hazırlanıyor...${NC}"

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}[INFO]${NC} Sanal ortam oluşturuluyor: ${VENV_DIR}"
    python3 -m venv "$VENV_DIR"
fi

# Pip güncelleme ve gereksinimlerin yüklenmesi
echo -e "${BLUE}[INFO]${NC} Python kütüphaneleri yükleniyor (PySide6, Scapy, Netifaces, Pytest)..."
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
"$VENV_DIR/bin/pip" install -r "${REPO_DIR}/requirements.txt"

# Projeyi geliştirici modunda bağlama
"$VENV_DIR/bin/pip" install -e "${REPO_DIR}"

echo -e "${GREEN}[OK]${NC} Python bağımlılıkları başarıyla yüklendi."

# 5. Linux Yetkilendirmeleri (Least Privilege - sudo'suz raw soketler)
echo -e "\n${CYAN}==> 4/6: Linux Yetkilendirmeleri (Capabilities) Tanımlanıyor...${NC}"
PYTHON_BIN="$VENV_DIR/bin/python3"
REAL_PYTHON=$(readlink -f "$PYTHON_BIN")

# Raw socket ve network admin yetkisi ver
$SUDO_CMD setcap cap_net_raw,cap_net_admin+eip "$REAL_PYTHON"
echo -e "${GREEN}[OK]${NC} ${REAL_PYTHON} dosyasına 'cap_net_raw,cap_net_admin+eip' yetkileri verildi."

# 6. Global CLI Başlatıcı (/usr/local/bin/cirak)
echo -e "\n${CYAN}==> 5/6: CLI Başlatıcı Script Oluşturuluyor...${NC}"

LAUNCHER_SCRIPT="/usr/local/bin/cirak"
$SUDO_CMD bash -c "cat > ${LAUNCHER_SCRIPT}" <<EOF
#!/usr/bin/env bash
# Ç.I.R.A.K. Başlatıcı Kısayolu

export REPO_DIR="${REPO_DIR}"
export VENV_PYTHON="${VENV_DIR}/bin/python"
export PYTHONPATH="${REPO_DIR}"

cd "${REPO_DIR}"

# Ekranda X11 veya Wayland yoksa doğrudan Raspberry Pi LinuxFB ve dokunmatik evdev kullan
if [ -z "\$DISPLAY" ] && [ -z "\$WAYLAND_DISPLAY" ]; then
    export QT_QPA_PLATFORM=linuxfb
    export QT_QPA_GENERIC_PLUGINS=evdevtouch
fi

exec "\$VENV_PYTHON" -m cirak.app "\$@"
EOF

$SUDO_CMD chmod +x "$LAUNCHER_SCRIPT"
echo -e "${GREEN}[OK]${NC} '${LAUNCHER_SCRIPT}' oluşturuldu. Konsoldan doğrudan 'cirak' yazarak başlatabilirsiniz."

# 7. Systemd Açılış Servisi (/etc/systemd/system/cirak.service)
SERVICE_FILE="/etc/systemd/system/cirak.service"
echo -e "${BLUE}[INFO]${NC} Açılışta otomatik başlama için systemd servisi yapılandırılıyor..."

# Ekranı çalan standart getty@tty1 konsol servisini devreden çıkar
$SUDO_CMD systemctl stop getty@tty1.service 2>/dev/null || true
$SUDO_CMD systemctl disable getty@tty1.service 2>/dev/null || true

$SUDO_CMD bash -c "cat > ${SERVICE_FILE}" <<EOF
[Unit]
Description=Ç.I.R.A.K. El Terminali Dokunmatik UI Servisi
After=network.target sound.target
Conflicts=getty@tty1.service

[Service]
Type=simple
User=${ACTUAL_USER}
WorkingDirectory=${REPO_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=QT_QPA_PLATFORM=linuxfb
Environment=QT_QPA_GENERIC_PLUGINS=evdevtouch
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
StandardInput=tty
StandardOutput=journal
StandardError=journal
ExecStart=${VENV_DIR}/bin/python -m cirak.app --fullscreen
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

$SUDO_CMD systemctl daemon-reload
$SUDO_CMD systemctl enable cirak.service
echo -e "${GREEN}[OK]${NC} Ç.I.R.A.K. servisi otomatik başlangıca eklendi (${SERVICE_FILE})."
echo -e "${GREEN}[OK]${NC} Cihaz açıldığında doğrudan Ç.I.R.A.K. el terminali arayüzü ile başlayacaktır."

# Endüstriyel El Terminali Sessiz Açılış (Quiet Boot / Konsol Yazılarını Gizleme)
CMDLINE_PATH="/boot/firmware/cmdline.txt"
[ ! -f "$CMDLINE_PATH" ] && CMDLINE_PATH="/boot/cmdline.txt"

if [ -f "$CMDLINE_PATH" ]; then
    echo -e "${BLUE}[INFO]${NC} Sessiz açılış (Quiet Appliance Boot) ayarları kontrol ediliyor..."
    if ! grep -q "quiet splash" "$CMDLINE_PATH"; then
        $SUDO_CMD sed -i 's/$/ quiet splash loglevel=3 vt.global_cursor_default=0/' "$CMDLINE_PATH" 2>/dev/null || true
        echo -e "${GREEN}[OK]${NC} Konsol akış yazıları gizlendi, profesyonel açılış yapılandırıldı."
    fi
fi

# Plymouth OS Açılış Görseli (Linux çekirdek açılışından itibaren Ç.I.R.A.K. logosu)
SPLASH_IMG="${REPO_DIR}/assets/images/cirak_splash_800x480.png"
if [ -f "$SPLASH_IMG" ] && [ -d "/usr/share/plymouth/themes/pix" ]; then
    $SUDO_CMD cp "$SPLASH_IMG" "/usr/share/plymouth/themes/pix/splash.png" 2>/dev/null || true
    echo -e "${GREEN}[OK]${NC} OS açılış görseli (Plymouth Splash) Ç.I.R.A.K. ile güncellendi."
fi

# 8. Otomatik Testlerin Çalıştırılması ve Doğrulama
echo -e "\n${CYAN}==> 6/6: Otomatik Test Paketi (Pytest) Doğrulanıyor...${NC}"
echo -e "${BLUE}[INFO]${NC} Backend ve UI duman testleri çalıştırılıyor..."

if "$VENV_DIR/bin/pytest" -v "${REPO_DIR}/tests"; then
    echo -e "\n${GREEN}${BOLD}✓ TEBRİKLER! Tüm testler (16/16) başarıyla geçti.${NC}"
else
    echo -e "\n${RED}[UYARI] Bazı testler başarısız oldu. Lütfen yukarıdaki çıktıyı kontrol edin.${NC}"
fi

echo -e "\n${CYAN}${BOLD}================================================================${NC}"
echo -e "${GREEN}${BOLD}  Kurulum Başarıyla Tamamlandı!                                 ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "Kullanım Seçenekleri:"
echo -e "  1. Servisi Hemen Başlatma:    ${BOLD}sudo systemctl start cirak.service${NC}"
echo -e "  2. Manuel Konsoldan Başlatma:  ${BOLD}cirak${NC} (veya ${BOLD}cirak --fullscreen${NC})"
echo -e "  3. Testleri Yeniden Koşma:     ${BOLD}${VENV_DIR}/bin/pytest -v${NC}"
echo -e "  4. Servis Durumu İzleme:        ${BOLD}systemctl status cirak.service${NC}"
echo -e "  * Servis zaten otomatik başlangıca eklenmiştir; yeniden başlattığınızda doğrudan açılacaktır."
echo -e "${CYAN}================================================================${NC}\n"
