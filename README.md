<div align="center">

# 🎵 Music IoT LCD Visualizer

[![License: MIT](https://img.shields.io/badge/License-MIT-blueviolet.svg?style=for-the-badge)](./LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS-black?style=for-the-badge&logo=apple)]()
[![Arduino](https://img.shields.io/badge/Arduino-Compatible-00979D?style=for-the-badge&logo=arduino&logoColor=white)]()
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)]()
[![Flask](https://img.shields.io/badge/Flask-Dashboard-000000?style=for-the-badge&logo=flask&logoColor=white)]()

</div>

Project ini menghubungkan Python di macOS dengan Arduino untuk membuat dashboard LCD 16x2 berbasis I2C. Saat Apple Music memutar lagu, LCD menampilkan judul lagu berjalan, visualizer audio 16-band logaritmik, dan LED yang bereaksi terhadap kick drum dengan gaya lighting konser. Saat tidak ada lagu yang diputar, LCD berubah menjadi monitor jam, tanggal, CPU, dan RAM. Semua data juga ditampilkan secara real-time di web dashboard bertema audio console.

## Fitur

- Menampilkan judul lagu dari Apple Music dengan scrolling text.
- Visualizer spectrum 16-band logaritmik di LCD 16x2.
- **Hardware-accelerated Smooth LED Fading** — decay eksponensial langsung di Arduino (60fps) untuk efek concert lighting yang sangat natural.
- **Beat detection tingkat lanjut** menggunakan spectral flux + adaptive median threshold (fokus kick drum 40-100Hz).
- **Real-time BPM Detector** — menghitung BPM secara presisi dengan sistem cooldown.
- Mode monitor otomatis saat musik pause atau Apple Music tidak berjalan (Jam, Tanggal, CPU, RAM).
- Web dashboard real-time bertema audio console di `http://localhost:5050`.
- **Fitur Premium Web Dashboard:**
  - **Real Album Art:** Mengambil cover album lagu yang sedang diputar secara otomatis dari iTunes Search API.
  - **Play History:** Mencatat otomatis riwayat lagu yang diputar ke `play_history.json`.
  - **Beat Flash Overlay:** Efek visual kedipan cahaya pada layar web yang tersinkronisasi dengan bass lagu.
  - Akses dashboard dari perangkat lain di jaringan WiFi yang sama.
- Konfigurasi serial port dan audio device lewat environment variable.

## Hardware

- Arduino Uno/Nano atau board kompatibel.
- LCD 16x2 I2C.
- LED + resistor.
- Kabel USB untuk koneksi serial Arduino ke laptop.

## Wiring

| Komponen    | Arduino           |
| ----------- | ----------------- |
| LCD SDA     | A4                |
| LCD SCL     | A5                |
| LCD VCC     | 5V                |
| LCD GND     | GND               |
| LED positif | D9 lewat resistor |
| LED negatif | GND               |

Catatan: pada beberapa board, pin I2C bisa berbeda. Cek dokumentasi board yang dipakai.

## Struktur Project

```text
.
├── music_sync.py
├── web_dashboard.py
├── requirements.txt
├── templates/
│   └── dashboard.html
├── sketch_jun21a/
│   └── sketch_jun21a.ino
└── README.md
```

## Instalasi Arduino

1. Buka Arduino IDE.
2. Install library `LiquidCrystal_I2C` dari Library Manager.
3. Buka file `sketch_jun21a/sketch_jun21a.ino`.
4. Pastikan alamat LCD sesuai. Default project ini memakai:

```cpp
LiquidCrystal_I2C lcd(0x27, 16, 2);
```

5. Upload sketch ke Arduino.

Jika LCD tidak tampil, coba scan alamat I2C. Alamat umum biasanya `0x27` atau `0x3F`.

## Instalasi Python

Project ini memakai Python 3.9+.

1. Buat virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependency:

```bash
pip install -r requirements.txt
```

3. Cek port Arduino:

```bash
ls /dev/cu.*
```

4. Jalankan script:

```bash
python music_sync.py
```

## Konfigurasi

Default konfigurasi ada di `music_sync.py`:

```python
SERIAL_PORT = "/dev/cu.usbserial-A5069RR4"
BAUD_RATE = 115200
AUDIO_INPUT_DEVICE_INDEX = 1
```

Untuk mengganti tanpa edit file, pakai environment variable:

```bash
MUSIC_IOT_SERIAL_PORT=/dev/cu.usbmodem1101 python music_sync.py
```

```bash
MUSIC_IOT_AUDIO_DEVICE_INDEX=0 python music_sync.py
```

Atau gabungkan:

```bash
MUSIC_IOT_SERIAL_PORT=/dev/cu.usbmodem1101 MUSIC_IOT_AUDIO_DEVICE_INDEX=0 python music_sync.py
```

## Cara Kerja

Python membaca status Apple Music lewat AppleScript. Jika lagu sedang berjalan, Python mengirim judul lagu:

```text
TXT:Judul Lagu - Artist
```

Setelah itu Python membaca input audio, melakukan FFT dengan NumPy menggunakan 16 logarithmic frequency bands (20Hz – 20kHz), lalu mengirim data visualizer:

```text
0,1,2,3,4,5,6,7,8,7,6,5,4,3,2,1|180
```

Bagian sebelum `|` adalah tinggi 16 kolom LCD. Bagian setelah `|` adalah brightness LED.

### Beat Detection & Smooth LED Fading

Sistem ini menggunakan algoritma deteksi *beat* kelas profesional:

1. **Bass-only spectral flux** — mendeteksi lonjakan energi (onset) hanya di area frekuensi kick drum, mengabaikan vokal dan melodi.
2. **Adaptive median threshold** — sensitivitas beradaptasi secara dinamis terhadap keras/pelannya lagu (anti-bocor).
3. **BPM Detector dengan Cooldown** — mengkalkulasi jarak antar ketukan bass untuk menemukan BPM lagu secara presisi.
4. **Zero-Latency Execution** — Transmisi serial sangat cepat, dan efek redup (decay) LED ditangani secara independen oleh Arduino di 60fps untuk transisi super mulus.

### Mode Monitor

Jika musik tidak berjalan, Python mengirim data sistem:

```text
SYS:JAM,TANGGAL,CPU,RAM
```

## Troubleshooting

### Gagal tersambung ke Arduino

- Pastikan Arduino sudah terhubung lewat USB.
- Pastikan serial port benar.
- Tutup Serial Monitor di Arduino IDE karena port serial hanya bisa dipakai satu program.

### Gagal membuka audio input device

- Ganti `MUSIC_IOT_AUDIO_DEVICE_INDEX`.
- Pastikan macOS memberi izin microphone/audio input untuk terminal yang dipakai.
- Jika memakai audio virtual seperti BlackHole, pastikan device sudah aktif.

### Apple Music tidak terbaca

- Project ini dibuat untuk macOS dan aplikasi Apple Music.
- Saat pertama kali jalan, macOS bisa meminta izin Automation untuk Terminal/Python mengontrol Music.

### LCD kosong

- Cek wiring SDA/SCL.
- Cek kontras LCD lewat trimpot modul I2C.
- Cek alamat I2C LCD, biasanya `0x27` atau `0x3F`.

## Web Dashboard

Saat `music_sync.py` dijalankan, web dashboard otomatis aktif di:

```
http://localhost:5050
```

Dashboard menggunakan tema premium *audio console* dengan antarmuka yang dinamis:

- **Now Playing Card** — Menampilkan judul lagu, artis, dan **Real Album Art** (terintegrasi API iTunes) dengan efek *glow* yang berdenyut sesuai *beat*.
- **Spectrum Analyzer** — Visualizer 16-band *real-time* dengan *peak hold indicator*, label frekuensi (Hz), dan skala dB. Di lengkapi juga dengan indikator **BPM (Beats Per Minute)**.
- **Beat Flash** — Kilatan layar interaktif di sisi kiri/kanan yang merespons pukulan bass lagu.
- **Play History** — Tabel riwayat lagu-lagu yang baru saja Anda putar secara lokal.
- **System Monitor** — Indikator jam digital, tanggal, CPU load, dan memory usage dengan animasi *fluid bar*.

Teknologi: Flask + Server-Sent Events (SSE) + Canvas API.

Untuk mengakses dashboard dari perangkat lain di jaringan WiFi yang sama:

```bash
# Cek IP laptop
ipconfig getifaddr en0

# Buka di browser HP
# http://<IP-LAPTOP>:5050
```

## Lisensi

```
MIT License

Copyright (c) 2026 FitoRifqi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

> [!NOTE]
> Project ini dibuat untuk tujuan pembelajaran dan eksperimen pribadi.
> Bebas digunakan, dimodifikasi, dan didistribusikan selama menyertakan
> copyright notice di atas.

---

<div align="center">

Made by **FitoRifqi** &nbsp;·&nbsp; Powered by Arduino & Python

</div>
