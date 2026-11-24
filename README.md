# Web2Apk (v1.2)

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0.0-blue.svg?style=for-the-badge" alt="Version 1.0">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Android-API%2026--34+-3DDC84.svg?style=for-the-badge&logo=android&logoColor=white" alt="Android API 26-34+">
  <img src="https://img.shields.io/badge/Gradle-9.3.1-02303A.svg?style=for-the-badge&logo=gradle&logoColor=white" alt="Gradle">
  <img src="https://img.shields.io/badge/License-Personal%20Use%20Only-red.svg?style=for-the-badge" alt="Personal Use Only">
</p>

<p align="center">
  <b><i>"Get rid of paid web to apk tools"</i></b><br>
  Developed by <b>Mohsin Khawaja</b> &bull; Follow on Instagram: <a href="https://www.instagram.com/csib.mohsin/"><b>@csib.mohsin</b></a>
</p>

---

## 📸 Compilation Dashboard & Overview

![Web2Apk Compilation Dashboard](Apk%20Generated%20.png)

**Web2Apk** is a 100% pure Python local web application and CLI utility that transforms live responsive websites or offline HTML/ZIP packages into production-ready, standalone Android APK packages.

Say goodbye to expensive monthly subscriptions, ad-injected APK wrappers, and third-party cloud generators that harvest your web assets. Web2Apk compiles genuine native APKs locally on your own machine using the official Android SDK and Gradle build chain.

---

## 🚀 Key Highlights & Capabilities

### 1. Dual Source Modes
- **🌐 Online Website URLs**: Turn responsive websites, SaaS portals, and Progressive Web Apps (PWAs) into native Android APKs.
- **📁 Offline Local HTML / ZIP Packages**: Package pure offline Single-Page Apps (HTML5, CSS, JavaScript, WebFonts, images) directly into `file:///android_asset/index.html`. Runs completely standalone without requiring an active internet connection.

### 2. High-Polish Light Dashboard
- Zero vertical page scroll (100vh fitted layout).
- Real-time environment diagnostic badges (Java JDK, Android SDK, Android Build Tools, Gradle Engine).
- Live launcher icon preview with drag-and-drop support.
- Fully editable **Android Package ID** (Application ID) with collision-resistant namespace sanitization (e.g. `com.app.instagram`).

### 3. Real-Time Streaming Build Console
- Line-by-line, unbuffered Gradle compile logs stream directly into your browser terminal.
- 6-Stage visual pipeline stepper:
  1. `Validate` &rarr; 2. `Prepare` &rarr; 3. `Icon` &rarr; 4. `Config` &rarr; 5. `Gradle` &rarr; 6. `APK Artifact`.
- One-click copy output logs and terminal clear controls.

### 4. Advanced Launcher Icon Engine
- Upload a single master image (`PNG`, `JPG`, `JPEG`, or `WEBP`).
- Automatically generates all Android mipmap densities:
  - `mipmap-mdpi` (48x48)
  - `mipmap-hdpi` (72x72)
  - `mipmap-xhdpi` (96x96)
  - `mipmap-xxhdpi` (144x144)
  - `mipmap-xxxhdpi` (192x192)
  - Adaptive launcher XML resources (`ic_launcher.xml`, `ic_launcher_round.xml`, `ic_launcher_background.xml`).

### 5. Production-Ready Native WebView Architecture
- Hardware accelerated graphics rendering.
- DOM Storage & Full JavaScript execution enabled.
- Integrated Android file picker (`<input type="file">` support for image/document uploads).
- Native protocol scheme routing for `tel:`, `mailto:`, `sms:`, and `whatsapp:`.
- Native Android back-button navigation with exit confirmation dialog on root view.
- Offline connection recovery interface with reload prompt.

---

## 📋 System Requirements & Prerequisites

Before running Web2Apk, ensure your system has the following installed:

| Component | Minimum Version | Notes |
| :--- | :--- | :--- |
| **Python** | `3.10+` | Make sure to check **"Add Python to PATH"** during install |
| **Java JDK** | `JDK 17` (Recommended) or `JDK 21` | Required by Gradle 9.3.1 and Android Gradle Plugin |
| **Android SDK** | API Level 26–34+ | Included with Android Studio or Command-Line Tools |

### Recommended JDK & SDK Setup:
1. **Java JDK 17**: Download and install [Eclipse Temurin 17](https://adoptium.net/temurin/releases/?version=17) or Oracle JDK 17. Ensure `JAVA_HOME` points to your JDK directory.
2. **Android SDK**: Install [Android Studio](https://developer.android.com/studio). Web2Apk automatically detects `ANDROID_HOME` at `%LOCALAPPDATA%\Android\Sdk` (Windows) or `~/Android/Sdk` (macOS/Linux).

---

## ⚡ Quick Start (Easy Setup)

### Option A: One-Click Launch (Windows)
Double-click `run.bat`.  
The script automatically verifies your Python environment, installs any missing dependencies from `requirements.txt`, launches the server, and opens `http://127.0.0.1:5000` in your default browser.

### Option B: Linux / macOS
Make the script executable and run:
```bash
chmod +x run.sh
./run.sh
```

### Option C: Manual Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/csibmohsin/web2apk.git
   cd web2apk
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the Web Console:
   ```bash
   python main.py
   ```
   Open `http://127.0.0.1:5000` in your web browser.

---

## 🖥️ Headless CLI Usage

Web2Apk also includes a full command-line interface for automated builds and CI/CD pipelines:

```bash
# Build APK from a live URL:
python main.py --cli --name "My Portal" --url "https://example.com" --icon "assets/logo.png"

# Build APK from a local offline HTML/ZIP file:
python main.py --cli --name "Offline Game" --html "path/to/game.zip" --package-id "com.game.offline"

# Specify custom output directory:
python main.py --cli --name "Docs" --url "https://docs.mycompany.com" --output "C:/Builds"
```

---

## 📂 Project Structure

```text
web2apk/
│
├── generator/                    # Core Python generation & build engine
│   ├── apk_generator.py          # Pipeline orchestrator
│   ├── build_manager.py          # Environment detector & Gradle subprocess runner
│   ├── icon_processor.py         # Multi-density mipmap & adaptive icon scaler
│   ├── package_generator.py      # App name & namespace sanitizer
│   └── template_manager.py       # Isolated build workspace creator
│
├── template/                     # Master Android Gradle & WebView template
│   └── android_webview/          # Production Android WebView source code
│
├── templates/                    # Web Console UI
│   └── index.html                # Light-themed, zero-scroll web interface
│
├── Generated_APKs/               # Default output directory for compiled APKs
├── run.bat                       # One-click Windows runner & auto-installer
├── run.sh                        # One-click Linux/macOS runner
├── requirements.txt              # Pure Python requirements (Flask, Pillow)
├── Apk Generated .png            # UI preview screenshot
└── main.py                       # Application entry point (Web & CLI)
```

---

## 👤 Author & Socials

- **Developer**: **Mohsin Khawaja**
- **Instagram**: [@csib.mohsin](https://www.instagram.com/csib.mohsin/)
- **GitHub**: [@csibmohsin](https://github.com/csibmohsin)

---

## 📄 License & Terms of Use

This project is licensed under the **Personal & Non-Commercial License** ([LICENSE](LICENSE)) &bull; Copyright &copy; 2026 **Mohsin Khawaja**.

- ✅ **Permitted**: Free for personal, educational, research, and non-commercial usage.
- ❌ **Prohibited**: Commercial use, selling, redistribution for profit, licensing, or inclusion in paid products/services is strictly prohibited.
