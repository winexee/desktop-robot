<div align="center">

<img src="assets/robot_supurge.png" alt="Masaüstü Robot Süpürge Logosu" width="120"/>

# Masaüstü Robot Süpürge

**Dağınık masaüstünüzü saniyeler içinde, akıcı bir animasyonla güvenle temizleyen akıllı masaüstü düzenleme asistanı.**

<br>

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](#)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-green.svg?logo=qt)](#)
[![Build](https://img.shields.io/badge/Build-Windows%20Setup.exe-brightgreen.svg)](#)
[![Linux](https://img.shields.io/badge/OS-Linux-orange.svg?logo=linux)](#)
[![Ubuntu](https://img.shields.io/badge/OS-Ubuntu-E95420.svg?logo=ubuntu&logoColor=white)](#)

</div>

---

## Özellikler

- **Arka Plan Masaüstü Taraması:** Büyük dosya sayılarında arayüzü dondurmadan masaüstünün üst düzeyindeki dosyaları tarar; gizli dosyaları, sembolik bağlantıları ve sistem dosyalarını güvenle ayırır. Alt klasörler taranmaz ve mevcut klasör yapınız korunur.
- **Çok Sayfalı Modern Koyu Tema Arayüzü:** Discord / Windows 11 Fluent esintili, sol kenar çubuklu (Kategori Kuralları, Hedef Klasör, Güvenlik ve Gelişmiş, Hakkında) ve tamamen opak arayüz.
- **Geri Dönüşüm Kutusu Güvenliği:** Varsayılan silme işlemi dosyaları `send2trash` ile işletim sisteminin Geri Dönüşüm Kutusu'na gönderir. Kalıcı silme yalnızca Güvenlik sekmesinden açıkça etkinleştirildiğinde ve işlem öncesinde ek onay kutusu işaretlendiğinde çalışır.
- **İşlem Özeti Onayı ve İptal Desteği:** Temizlik başlamadan önce taşınacak, çöp kutusuna gidecek, kalıcı silinecek ve atlanacak dosya sayılarını gösteren özet onay ekranı açılır. Temizlik sırasında "İptal" butonuyla işlem güvenle durdurulabilir.
- **Etkileşimli Robot Animasyonu:** Robot hedeflerine doğru ilerleyerek dosyaları eşzamanlı kuyrukla işler; boşta veya gizliyken zamanlayıcıyı durdurarak CPU kullanımını sıfıra indirir.
- **Detaylı Temizlik Raporu:** Taşınan, çöp kutusuna giden, kalıcı silinen, atlanan ve başarısız/iptal edilen tüm dosyaları, kategori bazlı ilerleme çubuklarını ve taramada atlanan klasör/dosya sayılarını şeffaf biçimde raporlar.
- **Katı Hedef Klasör Doğrulaması:** Masaüstü'nün kendisi, kök dizinler (`/`, `C:\`), kullanıcı ana dizini, sistem klasörleri (`Windows`, `System32`, `/etc`, `/usr` vb.) veya yazma izni olmayan dizinler hedef klasör olarak seçilemez.

---

## İndirme ve Kurulum

İşletim sisteminize uygun olan seçeneği tercih edin:

### Windows İçin (Kurulum Sihirbazı)

Python kurulumu gerektirmez. `--onedir` paketleme ve Inno Setup ile hazırlanmış kurulum sihirbazını (`MasaustuRobotSupurge_Setup.exe`) indirebilirsiniz:

1. **[GitHub Actions sayfasına gidin](https://github.com/winexee/desktop-robot/actions)** ve listedeki en son **"Build and Test"** çalıştırmasına tıklayın.
2. Sayfanın en altındaki **"Artifacts"** bölümünden `MasaustuRobotSupurge-Setup` paketini indirin.
3. Arşiv içindeki `MasaustuRobotSupurge_Setup.exe` dosyasını çalıştırın ve kurulum sihirbazını tamamlayın (Başlat Menüsü ve isteğe bağlı Masaüstü kısayolu oluşturulur).
4. Uygulama açıldığında **Ayarlar** penceresinden kategori kurallarınızı, hedef klasörünüzü ve güvenlik tercihlerinizi belirleyin.
5. Sağ üstteki kontrol panelinden **"> Süpür"** butonuna basın.

### Linux (Ubuntu) İçin

Aşağıdaki komutları terminalinizde çalıştırarak uygulamayı kaynak koddan doğrudan başlatabilirsiniz:

```bash
git clone https://github.com/winexee/desktop-robot.git
cd desktop-robot
python3 -m venv .venv
source .venv/bin/activate
pip install PyQt6 send2trash
python3 main.py
```

---

## Proje Yapısı

```text
desktop-robot/
├── main.py               # Giriş noktası, kontrol paneli, onay penceresi ve orkestrasyon
├── config.py             # Kategoriler, atomik JSON ayarları, yol doğrulama, cross-platform yardımcılar
├── file_scanner.py       # Masaüstü tarayıcı, arka plan tarama iş parçacığı ve konum sağlayıcı
├── file_mover.py         # FileStatus, FileResult ve tek kuyruklu FileWorkerThread
├── robot_widget.py       # Şeffaf robot overlay animasyonu ve konuşma balonları
├── settings_dialog.py    # 4 sayfalı (Kategori Kuralları, Hedef, Güvenlik, Hakkında) koyu tema arayüz
├── report_dialog.py      # 3 sekmeli detaylı rapor penceresi ve kategori oran çubukları
├── installer.iss         # Windows kurulum sihirbazı (Inno Setup) betiği
├── generate_robot_png.py # Robot PNG ve çoklu çözünürlüklü Windows ICO üreteci
├── assets/
│   └── robot_supurge.png # Uygulama logosu ve robot görseli
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_file_mover.py
│   ├── test_file_scanner.py
│   └── test_ui_and_report.py
└── .github/workflows/
    └── build.yml         # Linux & Windows pytest doğrulaması ve Windows Setup.exe derlemesi
```

---

## Geliştirme ve Testler

Test paketi gerçek masaüstüne dokunmadan, yalnızca izole geçici klasörler (`tmp_path`) üzerinde çalışır:

```bash
pip install PyQt6 send2trash pytest
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -v
```
