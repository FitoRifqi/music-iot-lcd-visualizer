# Music IoT LCD Visualizer

Project ini menghubungkan Python di macOS dengan Arduino untuk membuat dashboard LCD 16x2 berbasis I2C. Saat Apple Music memutar lagu, LCD menampilkan judul lagu berjalan, visualizer audio, dan LED yang bereaksi terhadap bass. Saat tidak ada lagu yang diputar, LCD berubah menjadi monitor jam, tanggal, CPU, dan RAM.

## Fitur

- Menampilkan judul lagu dari Apple Music.
- Visualizer 16 kolom di LCD 16x2.
- LED PWM bereaksi terhadap bass musik.
- Mode monitor otomatis saat musik pause atau Apple Music tidak berjalan.
- Menampilkan jam, tanggal, CPU, dan RAM.
- Konfigurasi serial port dan audio device lewat environment variable.

## Hardware

- Arduino Uno/Nano atau board kompatibel.
- LCD 16x2 I2C.
- LED + resistor.
- Kabel USB untuk koneksi serial Arduino ke laptop.

## Wiring

| Komponen | Arduino |
| --- | --- |
| LCD SDA | A4 |
| LCD SCL | A5 |
| LCD VCC | 5V |
| LCD GND | GND |
| LED positif | D9 lewat resistor |
| LED negatif | GND |

Catatan: pada beberapa board, pin I2C bisa berbeda. Cek dokumentasi board yang dipakai.

## Struktur Project

```text
.
├── music_sync.py
├── requirements.txt
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

Python membaca status Apple Music lewat AppleScript. Jika lagu sedang berjalan, Python mengirim:

```text
TXT:Judul Lagu - Artist
```

Setelah itu Python membaca input audio, melakukan FFT dengan NumPy, lalu mengirim data visualizer:

```text
0,1,2,3,4,5,6,7,8,7,6,5,4,3,2,1|180
```

Bagian sebelum `|` adalah tinggi 16 kolom LCD. Bagian setelah `|` adalah brightness LED.

Jika musik tidak berjalan, Python mengirim data monitor:

```text
SYS:17:06,21 JUN,12,65
```

Formatnya adalah:

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

## Upload ke GitHub

Jika folder ini belum menjadi repository Git:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/NAMA_REPO.git
git push -u origin main
```

Ganti `USERNAME` dan `NAMA_REPO` sesuai akun GitHub kamu.

## Lisensi

Silakan gunakan dan modifikasi project ini untuk belajar atau pengembangan pribadi.
