import os
import subprocess
import time
from datetime import datetime

import numpy as np
import psutil
import pyaudio
import serial


SERIAL_PORT = os.getenv("MUSIC_IOT_SERIAL_PORT", "/dev/cu.usbserial-A5069RR4")
BAUD_RATE = int(os.getenv("MUSIC_IOT_BAUD_RATE", "115200"))
AUDIO_INPUT_DEVICE_INDEX = int(os.getenv("MUSIC_IOT_AUDIO_DEVICE_INDEX", "1"))

CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

HISTORY_SIZE = 50
THRESHOLD_MULTIPLIER = 1.4
MIN_BASS_AMPLITUDE = 30
SPECTRUM_COLUMNS = 16

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


def calculate_bass_brightness(bass_amplitude, history, current_brightness):
    history.append(bass_amplitude)
    if len(history) > HISTORY_SIZE:
        history.pop(0)

    history_average = np.mean(history)
    is_bass_hit = (
        bass_amplitude > history_average * THRESHOLD_MULTIPLIER
        and bass_amplitude > MIN_BASS_AMPLITUDE
    )

    if is_bass_hit:
        target_brightness = int(np.log10(bass_amplitude + 1) * 70) - 60
        return max(180, min(255, target_brightness))

    return max(0, current_brightness - 25)


def build_visualizer_packet(stream, bass_history, current_brightness):
    data = stream.read(CHUNK, exception_on_overflow=False)
    samples = np.frombuffer(data, dtype=np.int16)
    fft_data = np.abs(np.fft.fft(samples))[: CHUNK // 2]

    freq_resolution = RATE / CHUNK
    bass_low_idx = int(20 / freq_resolution)
    bass_high_idx = int(150 / freq_resolution)
    bass_frequencies = fft_data[bass_low_idx:bass_high_idx]
    bass_amplitude = np.mean(bass_frequencies) if len(bass_frequencies) else 0
    brightness = calculate_bass_brightness(
        bass_amplitude,
        bass_history,
        current_brightness,
    )

    columns = []
    for chunk in np.array_split(fft_data, SPECTRUM_COLUMNS):
        amplitude = np.mean(chunk)
        scaled_value = int(np.log10(amplitude + 1) * 2.5) - 4
        columns.append(str(max(0, min(8, scaled_value))))

    return f"{','.join(columns)}|{brightness}\n", brightness


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

    try:
        stream = open_audio_stream(audio)
    except OSError as error:
        audio.terminate()
        print(f"Gagal membuka audio input device: {error}")
        return

    try:
        arduino = open_serial_connection()
        print("Sistem Dashboard Premium (Clock & Fluid Monitor) Aktif!")
    except serial.SerialException as error:
        close_resources(audio, stream=stream)
        print(f"Gagal tersambung ke Arduino: {error}")
        return

    bass_history = []
    current_brightness = 0
    current_track_name = ""
    music_state = "IDLE"
    last_metadata_check = 0
    last_system_check = 0

    try:
        while True:
            now = time.time()

            if now - last_metadata_check > 1.5:
                status = get_now_playing()
                if status.startswith("PLAYING:"):
                    music_state = "PLAYING"
                    track_info = status.removeprefix("PLAYING:")
                    if track_info != current_track_name:
                        current_track_name = track_info
                        arduino.write(f"TXT:{current_track_name}\n".encode())
                else:
                    music_state = "MONITOR"
                    current_track_name = ""
                last_metadata_check = now

            if music_state == "PLAYING":
                packet, current_brightness = build_visualizer_packet(
                    stream,
                    bass_history,
                    current_brightness,
                )
                arduino.write(packet.encode())
                time.sleep(0.01)
                continue

            if now - last_system_check > 1.0:
                arduino.write(build_system_packet().encode())
                last_system_check = now
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nSistem dimatikan.")
    finally:
        close_resources(audio, stream=stream, arduino=arduino)


if __name__ == "__main__":
    main()
