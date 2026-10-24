import time
import board
import adafruit_dht


from gpiozero import (
    TrafficLights,
    Buzzer,
    Button,
    MotionSensor,
)


lampu = TrafficLights(
    red=17,
    yellow=27,
    green=22,
)


buzzer = Buzzer(25)


tombol_mute = Button(
    5,
    pull_up=True,
    bounce_time=0.1,
)


sensor_pir = MotionSensor(23)


dht_device = adafruit_dht.DHT11(
    board.D4,
    use_pulseio=False,
)


WAKTU_WARMUP_PIR = 60  # detik


BATAS_SUHU_TINGGI = 31.0
BATAS_LEMBAB_WASPADA = 75.0
BATAS_LEMBAB_KRITIS = 80.0


current_state = "INITIALIZING"
is_muted = False
pir_siap = False


def tekan_tombol_handler():
    global is_muted


    if current_state in ("WARNING", "CRITICAL", "MUTED"):
        is_muted = not is_muted


        status_teks = (
            "DIHENINGKAN (MUTED)"
            if is_muted
            else "AKTIF KEMBALI"
        )


        print(
            f"\n>>> [BUTTON DITEKAN] "
            f"Alarm Buzzer: {status_teks} <<<"
        )
    else:
        print(
            "\n>>> [BUTTON DITEKAN] "
            "Sistem belum dalam kondisi alarm. <<<"
        )




tombol_mute.when_pressed = tekan_tombol_handler


def periksa_warmup_pir(waktu_mulai):
    global pir_siap


    if pir_siap:
        return


    waktu_berjalan = time.monotonic() - waktu_mulai
    sisa = max(
        0,
        int(WAKTU_WARMUP_PIR - waktu_berjalan),
    )


    if waktu_berjalan >= WAKTU_WARMUP_PIR:
        pir_siap = True
        print(
            "\n[PIR SIAP] Sensor gerakan siap digunakan.\n"
        )
    else:
        print(
            f"\r[PIR WARM-UP] {sisa:02d} detik tersisa",
            end="",
            flush=True,
        )


def baca_semua_sensor():
    suhu = None
    kelembaban = None


    try:
        suhu = dht_device.temperature
        kelembaban = dht_device.humidity
    except RuntimeError:
        # Jika pembacaan gagal, coba lagi pada iterasi berikutnya.
        pass


    ada_gerakan = (
        sensor_pir.motion_detected
        if pir_siap
        else False
    )


    return suhu, kelembaban, ada_gerakan


def evaluasi_state(suhu, kelembaban, gerakan):
    global current_state, is_muted


    # Prioritas 1: kondisi kritis
    if (
        suhu >= BATAS_SUHU_TINGGI
        or kelembaban >= BATAS_LEMBAB_KRITIS
    ):
        state_baru = "CRITICAL"


    # Prioritas 2: kondisi peringatan
    elif (
        kelembaban >= BATAS_LEMBAB_WASPADA
        or gerakan
    ):
        state_baru = "WARNING"


    else:
        state_baru = "NORMAL"
        is_muted = False


    # Mute tidak mengubah kondisi sensor.
    if state_baru in ("WARNING", "CRITICAL") and is_muted:
        current_state = "MUTED"
    else:
        current_state = state_baru


    return current_state


def jalankan_output(state):
    # Hentikan pola output sebelumnya.
    buzzer.off()
    lampu.off()


    if state == "INITIALIZING":
        lampu.green.on()


    elif state == "NORMAL":
        lampu.green.on()


    elif state == "WARNING":
        lampu.yellow.on()


        buzzer.beep(
            on_time=0.2,
            off_time=0.8,
            background=True,
        )


    elif state == "CRITICAL":
        lampu.red.blink(
            on_time=0.2,
            off_time=0.2,
            background=True,
        )


        buzzer.beep(
            on_time=0.1,
            off_time=0.1,
            background=True,
        )


    elif state == "MUTED":
        lampu.yellow.on()
        lampu.red.on()
        buzzer.off()

def main():
    global current_state, pir_siap


    print("=== SISTEM MONITORING RUANG LAB/SERVER AKTIF ===")


    # Nilai awal sementara jika DHT11 belum berhasil dibaca.
    suhu_valid = 27.0
    lembab_valid = 60.0


    waktu_mulai = time.monotonic()
    status_output_terakhir = "INITIALIZING"


    # LED hijau sebagai indikator inisialisasi.
    jalankan_output("INITIALIZING")


    try:
        while True:
            periksa_warmup_pir(waktu_mulai)


            # DHT11 tetap dibaca selama warm-up PIR.
            suhu, kelembaban, gerakan = baca_semua_sensor()


            if suhu is not None and kelembaban is not None:
                suhu_valid = suhu
                lembab_valid = kelembaban


            # Selama warm-up, hijau tetap menyala kecuali
            # kondisi kritis suhu atau kelembapan terjadi.
            if not pir_siap:
                if (
                    suhu_valid >= BATAS_SUHU_TINGGI
                    or lembab_valid >= BATAS_LEMBAB_KRITIS
                ):
                    state_aktif = evaluasi_state(
                        suhu_valid,
                        lembab_valid,
                        False,
                    )
                else:
                    state_aktif = "INITIALIZING"
                    current_state = state_aktif
            else:
                state_aktif = evaluasi_state(
                    suhu_valid,
                    lembab_valid,
                    gerakan,
                )


            # Ubah output hanya saat status berubah.
            if state_aktif != status_output_terakhir:
                jalankan_output(state_aktif)
                status_output_terakhir = state_aktif


            if not pir_siap:
                status_pir = "WARM-UP"
            elif gerakan:
                status_pir = "GERAK"
            else:
                status_pir = "AMAN"


            print(
                f"[STATE: {state_aktif:12s}] "
                f"Suhu: {suhu_valid:.1f}C | "
                f"Lembab: {lembab_valid}% | "
                f"PIR: {status_pir:7s} | "
                f"Mute: {is_muted}"
            )


            time.sleep(2.0)


    except KeyboardInterrupt:
        print(
            "\nMenghentikan program dan membersihkan pin GPIO..."
        )


    finally:
        buzzer.off()
        lampu.off()


        tombol_mute.close()
        sensor_pir.close()


        dht_device.exit()


        buzzer.close()
        lampu.close()


        print("Semua output dimatikan dan GPIO dibersihkan.")




if __name__ == "__main__":
    main()