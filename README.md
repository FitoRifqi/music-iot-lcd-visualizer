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
- LED PWM concert-style dengan kick drum detection (40-100Hz).
- Beat detection menggunakan spectral flux + adaptive median threshold.
- Mode monitor otomatis saat musik pause atau Apple Music tidak berjalan.
- Menampilkan jam, tanggal, CPU, dan RAM.
- Web dashboard real-time bertema audio console di `http://localhost:5050`.
- LED strip meter, VU meter, dan spectrum analyzer di browser.
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

### Beat Detection

LED menggunakan algoritma concert-style beat detection:

1. **Bass-only spectral flux** — perubahan energi dihitung hanya di range 0-150Hz, mengabaikan hi-hat, cymbal, dan vocal.
2. **Kick drum focus (40-100Hz)** — menggunakan peak amplitude (bukan mean) untuk mendeteksi pukulan kick drum dengan akurat.
3. **Adaptive median threshold** — threshold otomatis menyesuaikan volume dan tempo lagu.
4. **Beat cooldown 80ms** — mencegah ghost trigger / double-flash.
5. **Concert-style response** — flash instan ke 210-255 saat beat terdeteksi, lalu blackout cepat (decay 0.50).

Jika musik tidak berjalan, Python mengirim data monitor:

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

Dashboard menggunakan tema audio console dengan tampilan:

- **Now Playing** — judul lagu dan artist dengan EQ bar animation.
- **Spectrum Analyzer** — visualizer 16-band real-time dengan peak hold indicator, label frekuensi (Hz), dan skala dB.
- **LED Output** — LED strip meter hijau/kuning/merah seperti mixer audio.
- **System Monitor** — jam, tanggal, CPU load, dan memory dengan VU meter bar.

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
