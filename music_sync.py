import json
import os
import re
import ssl
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

import numpy as np
import psutil
import pyaudio
import serial

from web_dashboard import create_shared_state, start_dashboard


SERIAL_PORT = os.getenv("MUSIC_IOT_SERIAL_PORT", "/dev/cu.usbserial-A5069RR4")
BAUD_RATE = int(os.getenv("MUSIC_IOT_BAUD_RATE", "115200"))
AUDIO_INPUT_DEVICE_INDEX = int(os.getenv("MUSIC_IOT_AUDIO_DEVICE_INDEX", "1"))

CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

HISTORY_SIZE = 50
FLUX_THRESHOLD_MULTIPLIER = 1.8
MIN_BASS_AMPLITUDE = 25
SPECTRUM_COLUMNS = 16
DECAY_FACTOR = 0.55
SUB_BASS_UPPER = 60
MID_BASS_UPPER = 150
FLUX_HISTORY_SIZE = 60
KICK_DRUM_LOW = 40
KICK_DRUM_HIGH = 100

# Logarithmic frequency bands (Hz) — lebih banyak kolom untuk bass/low-mid
# seperti lighting setup asli: bass dominan, treble compressed
LOG_FREQ_EDGES = [
    20, 35, 50, 70, 100, 140, 200, 300,
    450, 650, 1000, 1500, 2500, 4000, 7000, 11000, 20000,
]

MONTH_NAMES = {
    1: "JAN",
    2: "FEB",
    3: "MAR",
    4: "APR",
    5: "MEI",
    6: "JUN",
    7: "JUL",
    8: "AGU",
    9: "SEP",
    10: "OKT",
    11: "NOV",
    12: "DES",
}

APPLE_SCRIPT = """
tell application "System Events"
    if "Music" is in (name of every process) then
        tell application "Music"
            if player state is playing then
                return "PLAYING:" & name of current track & " - " & artist of current track
            else
                return "PAUSED"
            end if
        end tell
    else
        return "IDLE"
    end if
end tell
"""


def get_now_playing():
    try:
        result = subprocess.run(
            ["osascript", "-e", APPLE_SCRIPT],
            capture_output=True,
            check=False,
            text=True,
        )
        return result.stdout.strip()
    except OSError:
        return "IDLE"


def fetch_album_art_url(track_name: str) -> str:
    """Fetch album artwork URL dari iTunes Search API (public, no auth)."""
    try:
        # "Song - Artist" → "Song Artist" supaya iTunes matching lebih akurat
        search_term = track_name.replace(" - ", " ")
        query = urllib.parse.quote(search_term)
        url = (
            "https://itunes.apple.com/search"
            f"?term={query}&media=music&entity=song&limit=1"
        )
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(url, timeout=6, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        if not results:
            return ""
        art = results[0].get("artworkUrl100", "")
        if not art:
            return ""
        # Upgrade ke 600x600 — regex replace NxNbb dengan 600x600bb
        return re.sub(r"\d+x\d+bb", "600x600bb", art)
    except Exception:
        return ""


def open_audio_stream(audio):
    return audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=AUDIO_INPUT_DEVICE_INDEX,
        frames_per_buffer=CHUNK,
    )


def open_serial_connection():
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0)
    time.sleep(2)
    return arduino


def calculate_spectral_flux(current_fft, previous_fft):
    """Hitung spectral flux: jumlah kenaikan energi antar frame.

    Hanya menghitung kenaikan (half-wave rectification) supaya
    lebih sensitif terhadap onset/serangan bass.
    """
    if previous_fft is None or len(previous_fft) != len(current_fft):
        return 0.0
    diff = current_fft - previous_fft
    return float(np.sum(np.maximum(diff, 0)))


def calculate_bass_brightness(
    kick_amp, sub_bass_amp, mid_bass_amp, flux, flux_history,
    current_brightness,
):
    """Concert-style beat detection: flash tajam + blackout cepat.

    Fokus di kick drum (40-100Hz). Flash langsung ke 255 saat beat
    terdeteksi, lalu blackout cepat (decay 0.55) supaya kontras
    antara hit dan silence sangat jelas, seperti lighting konser.
    """
    flux_history.append(flux)
    if len(flux_history) > FLUX_HISTORY_SIZE:
        flux_history.pop(0)

    flux_median = float(np.median(flux_history)) if flux_history else 0.0
    flux_threshold = flux_median * FLUX_THRESHOLD_MULTIPLIER

    # Kick drum dominan, sub-bass secondary
    combined_bass = kick_amp * 2.0 + sub_bass_amp * 0.8 + mid_bass_amp * 0.3
    is_bass_hit = flux > flux_threshold and combined_bass > MIN_BASS_AMPLITUDE

    if is_bass_hit:
        # Concert-style: langsung full brightness, semakin kuat semakin terang
        hit_strength = min(1.0, combined_bass / 200.0)
        target = int(200 + hit_strength * 55)  # range 200-255
        return min(255, target), True

    # Blackout cepat — kontras tajam seperti strobe lighting
    return max(0, int(current_brightness * DECAY_FACTOR)), False


def calculate_bpm(beat_timestamps: list, now: float) -> int:
    """Estimasi BPM dari interval antar beat (window 8 detik terakhir)."""
    recent = [t for t in beat_timestamps if now - t < 8.0]
    if len(recent) < 2:
        return 0
    intervals = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
    if not intervals:
        return 0
    avg_interval = float(np.mean(intervals))
    if avg_interval < 0.15:  # lebih dari 400 BPM = noise
        return 0
    bpm = 60.0 / avg_interval
    return int(round(min(200, max(40, bpm))))


def build_visualizer_packet(
    stream, flux_history, current_brightness, previous_fft, bpm: int = 0
):
    data = stream.read(CHUNK, exception_on_overflow=False)
    samples = np.frombuffer(data, dtype=np.int16)
    fft_data = np.abs(np.fft.fft(samples))[: CHUNK // 2]

    flux = calculate_spectral_flux(fft_data, previous_fft)

    freq_resolution = RATE / CHUNK
    sub_bass_idx = int(20 / freq_resolution)
    kick_low_idx = int(KICK_DRUM_LOW / freq_resolution)
    kick_high_idx = int(KICK_DRUM_HIGH / freq_resolution)
    sub_bass_upper_idx = int(SUB_BASS_UPPER / freq_resolution)
    mid_bass_upper_idx = int(MID_BASS_UPPER / freq_resolution)

    kick_freq = fft_data[kick_low_idx:kick_high_idx]
    sub_bass_freq = fft_data[sub_bass_idx:sub_bass_upper_idx]
    mid_bass_freq = fft_data[sub_bass_upper_idx:mid_bass_upper_idx]

    kick_amp = float(np.mean(kick_freq)) if len(kick_freq) else 0.0
    sub_bass_amp = float(np.mean(sub_bass_freq)) if len(sub_bass_freq) else 0.0
    mid_bass_amp = float(np.mean(mid_bass_freq)) if len(mid_bass_freq) else 0.0

    brightness, is_beat = calculate_bass_brightness(
        kick_amp,
        sub_bass_amp,
        mid_bass_amp,
        flux,
        flux_history,
        current_brightness,
    )

    columns = []
    column_values = []
    freq_res = RATE / CHUNK
    for i in range(SPECTRUM_COLUMNS):
        low_hz = LOG_FREQ_EDGES[i]
        high_hz = LOG_FREQ_EDGES[i + 1]
        low_bin = max(1, int(low_hz / freq_res))
        high_bin = min(len(fft_data), int(high_hz / freq_res))
        if high_bin <= low_bin:
            high_bin = low_bin + 1
        band = fft_data[low_bin:high_bin]
        amplitude = float(np.mean(band)) if len(band) else 0.0
        scaled_value = int(np.log10(amplitude + 1) * 2.0) - 3
        clamped = max(0, min(8, scaled_value))
        columns.append(str(clamped))
        column_values.append(clamped)

    return (
        f"{','.join(columns)}|{brightness}|{bpm}\n",
        brightness,
        fft_data,
        column_values,
        is_beat,
    )


def build_system_packet():
    now = datetime.now()
    time_text = now.strftime("%H:%M")
    date_text = f"{now.strftime('%d')} {MONTH_NAMES.get(now.month, 'JAN')}"
    cpu_usage = int(psutil.cpu_percent())
    ram_usage = int(psutil.virtual_memory().percent)
    return f"SYS:{time_text},{date_text},{cpu_usage},{ram_usage}\n"


def close_resources(audio, stream=None, arduino=None):
    if stream is not None:
        stream.stop_stream()
        stream.close()
    audio.terminate()
    if arduino is not None:
        arduino.close()


def main():
    audio = pyaudio.PyAudio()
    stream = None
    arduino = None

    # Inisialisasi baseline psutil supaya pembacaan pertama tidak 0%
    psutil.cpu_percent()

    shared_state = create_shared_state()
    shared_state.load_history()

    dashboard_thread = threading.Thread(
        target=start_dashboard,
        args=(shared_state,),
        daemon=True,
    )
    dashboard_thread.start()

    try:
        stream = open_audio_stream(audio)
    except OSError as error:
        audio.terminate()
        print(f"Gagal membuka audio input device: {error}")
        return

    try:
        arduino = open_serial_connection()
        print("Sistem Dashboard Premium (Clock & Fluid Monitor) Aktif!")
        print("Web Dashboard: http://localhost:5050")
    except serial.SerialException as error:
        close_resources(audio, stream=stream)
        print(f"Gagal tersambung ke Arduino: {error}")
        return

    flux_history = []
    current_brightness = 0
    current_track_name = ""
    music_state = "IDLE"
    last_metadata_check = 0
    last_system_check = 0
    previous_fft = None
    beat_timestamps: list = []
    current_bpm = 0
    last_bpm_beat_time: float = 0.0

    try:
        while True:
            now = time.time()

            if now - last_metadata_check > 1.5:
                status = get_now_playing()
                if status.startswith("PLAYING:"):
                    music_state = "PLAYING"
                    track_info = status.removeprefix("PLAYING:")
                    if track_info != current_track_name:
                        if current_track_name:
                            shared_state.add_to_history(
                                current_track_name,
                                datetime.now().strftime("%H:%M"),
                            )
                        current_track_name = track_info
                        arduino.write(f"TXT:{current_track_name}\n".encode())
                        # Fetch album art di background — non-blocking
                        _name = current_track_name
                        threading.Thread(
                            target=lambda n=_name: shared_state.update(
                                artwork_url=fetch_album_art_url(n)
                            ),
                            daemon=True,
                        ).start()
                    shared_state.update(
                        mode="PLAYING",
                        track=current_track_name,
                    )
                else:
                    if current_track_name:
                        shared_state.add_to_history(
                            current_track_name,
                            datetime.now().strftime("%H:%M"),
                        )
                    music_state = "MONITOR"
                    current_track_name = ""
                    beat_timestamps.clear()
                    current_bpm = 0
                    last_bpm_beat_time = 0.0
                    shared_state.update(mode="MONITOR", track="", bpm=0, artwork_url="")
                last_metadata_check = now

            # Selalu update system stats ke dashboard, apapun mode-nya
            if now - last_system_check > 1.0:
                now_dt = datetime.now()
                cpu = int(psutil.cpu_percent())
                ram = int(psutil.virtual_memory().percent)
                time_str = now_dt.strftime("%H:%M")
                date_str = f"{now_dt.strftime('%d')} {MONTH_NAMES.get(now_dt.month, 'JAN')}"

                shared_state.update(
                    cpu=cpu,
                    ram=ram,
                    time=time_str,
                    date=date_str,
                )

                if music_state != "PLAYING":
                    sys_packet = f"SYS:{time_str},{date_str},{cpu},{ram}\n"
                    arduino.write(sys_packet.encode())
                    shared_state.update(
                        visualizer=[0] * SPECTRUM_COLUMNS,
                        brightness=0,
                    )

                last_system_check = now

            if music_state == "PLAYING":
                packet, current_brightness, previous_fft, col_values, is_beat = (
                    build_visualizer_packet(
                        stream,
                        flux_history,
                        current_brightness,
                        previous_fft,
                        bpm=current_bpm,
                    )
                )
                if is_beat:
                    now_beat = time.time()
                    # Cooldown 300ms antar beat — cegah double-count pada transien cepat
                    if now_beat - last_bpm_beat_time >= 0.30:
                        last_bpm_beat_time = now_beat
                        beat_timestamps.append(now_beat)
                        if len(beat_timestamps) > 16:
                            beat_timestamps.pop(0)
                        new_bpm = calculate_bpm(beat_timestamps, now_beat)
                        if new_bpm > 0:
                            current_bpm = new_bpm
                arduino.write(packet.encode())
                shared_state.update(
                    visualizer=col_values,
                    brightness=current_brightness,
                    bpm=current_bpm,
                )
                time.sleep(0.01)
                continue

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nSistem dimatikan.")
    finally:
        close_resources(audio, stream=stream, arduino=arduino)


if __name__ == "__main__":
    main()

