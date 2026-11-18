<div align="center">
  <img src="assets/robot_supurge.png" alt="Robot Süpürge Logo" width="120"/>
  # 🤖 Masaüstü Robot Süpürge
  **Dağınık masaüstünüzü saniyeler içinde, eğlenceli bir animasyonla temizleyen akıllı asistan.**
  <br>
  [![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)](#)
  [![PyQt6](https://img.shields.io/badge/UI-PyQt6-green.svg?logo=qt)](#)
  [![Build](https://img.shields.io/badge/Build-Windows%20EXE-success.svg)](#)
  [![Linux](https://img.shields.io/badge/OS-Linux-orange.svg?logo=linux)](#)
  [![Ubuntu](https://img.shields.io/badge/OS-Ubuntu-E95420.svg?logo=ubuntu&logoColor=white)](#)
</div>

---

## ✨ Robot Ne Yapar? (Özellikler)

- 🔍 **Masaüstü Taraması:** Başlatıldığı anda masaüstünüzdeki tüm başıboş dosyaları tespit edip kendine hedef olarak belirler.
- 🤖 **İnteraktif Temizlik:** Ekranda hedeflerine doğru gezinir, dosyaların üzerine geldiğinde onları fiziksel olarak "yer" ve bu sırada esprili konuşma balonları çıkarır.
- 🗂️ **Akıllı Düzenleme:** Yuttuğu dosyaları uzantılarına (Resim, Belge, Uygulama vb.) göre ayırır ve hedef klasörlere düzenli bir şekilde yerleştirir.
- 🛡️ **Seçici Temizlik (Kurallar):** Hangi dosya türünün **Taşınacağını**, hangisinin anında **Silineceğini** veya hangisine **Dokunulmayacağını (Atla)** tamamen kontrol panelinden siz belirlersiniz.
- 🎨 **Karanlık Tema (Dark Mode):** Ayarlamaları yapmanız için Fluent Design / Discord esintili modern, gölgeli ve pürüzsüz geçişli bir arayüz sunar.

## 🚀 İndirme ve Kurulum

İşletim sisteminize uygun olan seçeneği tercih edin:

### 🪟 Windows İçin
Hiçbir kurulum veya Python bilgisi gerektirmez. Doğrudan tek tıklamayla çalışan **.exe** dosyasını indirebilirsiniz.

- 📥 **[main.exe Dosyasını İndir](https://github.com/winexee/desktop-robot/actions)** *(Sayfadaki en son "Build Windows EXE" işlemine tıklayıp en alttaki "Artifacts" bölümünden indirebilirsiniz)*
- İndirin, çift tıklayın ve sağ üstteki ⚙️ menüsünden ayarlarınızı yapıp **"▶ Süpür"**e basın!

### 🐧 Linux (Ubuntu) İçin
Aşağıdaki komutları terminalinize kopyalayarak projeyi kendi sisteminizde doğrudan çalıştırabilirsiniz:

```bash
# Projeyi bilgisayarınıza klonlayın
git clone [https://github.com/winexee/desktop-robot.git](https://github.com/winexee/desktop-robot.git)
cd desktop-robot

# Sanal ortam oluşturup kütüphaneleri yükleyin
python3 -m venv .venv
source .venv/bin/activate
pip install PyQt6

# Robotu çalıştırın
python3 main.py
```
