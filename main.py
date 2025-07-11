import cv2
import pyglet.media
from cvzone.FaceMeshModule import FaceMeshDetector
import pyfirmata
import csv
from datetime import datetime
import time
import requests

# --- Konfigurasi Bot Telegram ---
# Ganti dengan token bot Anda yang diperoleh dari @BotFather
TELEGRAM_BOT_TOKEN = '7488763111:AAGR6KCkLVyNHJeNSLCVMptVaM_rKHpb7HE'
# Ganti dengan Chat ID Anda yang diperoleh dari API getUpdates
TELEGRAM_CHAT_ID = '714455558'

# Jeda waktu (cooldown) untuk notifikasi Telegram untuk menghindari spam
NOTIFICATION_COOLDOWN_SECONDS = 60
# Variabel cooldown yang lebih spesifik untuk notifikasi motor DC
last_telegram_notification_time_motor_lvl1_down = 0  # Waktu terakhir notifikasi motor melambat
last_telegram_notification_time_motor_lvl2_stop = 0  # Waktu terakhir notifikasi motor berhenti
last_telegram_notification_time_safety_face_missing = 0  # Jeda waktu untuk notifikasi keselamatan (misal: wajah tidak terdeteksi)

# --- Konfigurasi Motor DC dan L298N ---
MOTOR_PWM_PIN = 9  # Pin PWM untuk kecepatan motor DC (misal: ENA/ENB pada L298N)
MOTOR_IN1_PIN = 10  # Pin input arah 1 (misal: IN1/IN3 pada L298N)
MOTOR_IN2_PIN = 11  # Pin input arah 2 (misal: IN2/IN4 pada L298N)

# Tingkat kecepatan PWM (0-255)
SPEED_MAX_ADJUSTED = 254  # Diubah dari 255 menjadi 254
SPEED_HALF_ADJUSTED = 127  # Diubah dari 128 menjadi 127
SPEED_STOP = 0

# Tingkat kecepatan motor DC saat ini: 0=berhenti, 1=setengah kecepatan, 2=kecepatan normal
motor_speed_level = 2  # Mulai dari kecepatan normal

# --- Variabel untuk Logika Pemulihan Kecepatan Motor DC ---
recovery_timer_active = False  # Menandakan apakah pengatur waktu pemulihan sedang aktif
recovery_start_time = 0  # Timestamp ketika pengatur waktu pemulihan dimulai
RECOVERY_DELAY_STOP_TO_HALF = 5  # Durasi (detik) untuk pulih dari berhenti ke setengah kecepatan
RECOVERY_DELAY_HALF_TO_MAX = 5  # Durasi (detik) untuk pulih dari setengah kecepatan ke kecepatan maksimal

# Inisialisasi kamera
cap = cv2.VideoCapture(0)
cap.set(3, 1280)  # Atur lebar frame
cap.set(4, 720)  # Atur tinggi frame

# Periksa apakah kamera berhasil dibuka
if not cap.isOpened():
    print("ERROR: Gagal membuka kamera. Pastikan kamera terhubung dan tidak digunakan oleh aplikasi lain.")
    exit()  # Keluar dari program jika kamera tidak dapat dibuka

# Inisialisasi Detektor FaceMesh
detector = FaceMeshDetector(maxFaces=1)  # Deteksi maksimal 1 wajah

# Ambang batas (Threshold) dan penghitung (Counter) (EAR_THRESH akan dikalibrasi)
EAR_CONSEC_FRAMES = 40  # Jumlah frame berturut-turut untuk deteksi kantuk
MAR_THRESH = 0.65  # Ambang batas Mouth Aspect Ratio untuk deteksi menguap
MAR_CONSEC_FRAMES = 40  # Jumlah frame berturut-turut untuk deteksi menguap

# Variabel status deteksi kantuk dan menguap
breakcount_s, breakcount_y = 0, 0  # Penghitung frame berturut-turut untuk kantuk dan menguap
counter_s, counter_y = 0, 0  # Penghitung total kejadian kantuk dan menguap
state_s, state_y = False, False  # Bendera status untuk kejadian kantuk/menguap yang aktif (untuk buzzer/suara/notifikasi awal)
sleep_start_time = None  # Timestamp ketika kejadian kantuk dimulai
yawn_start_time = None  # Timestamp ketika kejadian menguap dimulai

# Muat Suara Alarm
sound = None  # Inisialisasi suara ke None
try:
    sound = pyglet.media.load("alarm.wav", streaming=False)
    print("Suara alarm 'alarm.wav' berhasil dimuat.")
except Exception as e:
    print(f"ERROR: Gagal memuat file suara 'alarm.wav': {e}")
    print("Pastikan file 'alarm.wav' ada di direktori yang sama dan tidak rusak.")

# Pengaturan Koneksi Arduino
buzzer_pin = None
motor_pwm_pin_obj = None
motor_in1_pin_obj = None
motor_in2_pin_obj = None

arduino_port = "COM5"  # Port COM yang terhubung ke Arduino
arduino_buzzer_pin_num = 7  # Pin digital untuk buzzer

try:
    board = pyfirmata.Arduino(arduino_port)
    # Penting: Mulai iterator agar pin PWM berfungsi dengan benar
    # Ini harus dilakukan setelah board diinisialisasi
    it = pyfirmata.util.Iterator(board)
    it.start()
    time.sleep(1)  # Tambahkan jeda 1 detik untuk memastikan komunikasi Firmata stabil

    # Inisialisasi pin buzzer
    buzzer_pin = board.get_pin(f'd:{arduino_buzzer_pin_num}:o')  # 'd' untuk digital, 'o' untuk output
    buzzer_pin.write(0)  # Pastikan buzzer mati di awal (LOW)
    print(f"Arduino terhubung di {arduino_port}.")
    print(f"Pin buzzer {arduino_buzzer_pin_num} diinisialisasi.")

    # Inisialisasi pin driver motor L298N
    motor_pwm_pin_obj = board.get_pin(f'd:{MOTOR_PWM_PIN}:p')  # 'p' untuk output PWM
    motor_in1_pin_obj = board.get_pin(f'd:{MOTOR_IN1_PIN}:o')
    motor_in2_pin_obj = board.get_pin(f'd:{MOTOR_IN2_PIN}:o')

    # Atur arah motor DC ke satu arah (misal: maju)
    motor_in1_pin_obj.write(1)  # HIGH
    motor_in2_pin_obj.write(0)  # LOW

    # Atur kecepatan awal motor DC ke kecepatan normal yang disesuaikan
    motor_pwm_pin_obj.write(SPEED_MAX_ADJUSTED / 255.0)  # Nilai PWM pyfirmata berkisar antara 0.0-1.0
    print(f"Motor DC diinisialisasi: PWM Pin {MOTOR_PWM_PIN}, IN1 {MOTOR_IN1_PIN}, IN2 {MOTOR_IN2_PIN}.")
    print(f"Kecepatan awal motor DC: NORMAL ({SPEED_MAX_ADJUSTED}).")

except Exception as e:
    print(f"ERROR: Gagal terhubung ke Arduino di {arduino_port}: {e}")
    print("Fungsi Arduino (buzzer dan motor DC) tidak akan aktif.")
    board = None
    buzzer_pin = None
    motor_pwm_pin_obj = None
    motor_in1_pin_obj = None
    motor_in2_pin_obj = None

# Definisikan landmark FaceMesh untuk mata dan mulut
left_eye_indices = [33, 160, 158, 133, 153, 144]
right_eye_indices = [362, 385, 387, 263, 373, 380]
mar_points = [61, 81, 13, 311, 308, 402, 14, 178]
faceId = left_eye_indices + right_eye_indices + mar_points  # Semua ID landmark relevan untuk digambar


# Fungsi untuk menghitung Eye Aspect Ratio (EAR)
def calculate_EAR(eye_points, face):
    # Hitung jarak Euclidean antara landmark mata vertikal
    vert1, _ = detector.findDistance(face[eye_points[1]], face[eye_points[5]])
    vert2, _ = detector.findDistance(face[eye_points[2]], face[eye_points[4]])
    # Hitung jarak Euclidean antara landmark mata horizontal
    hor, _ = detector.findDistance(face[eye_points[0]], face[eye_points[3]])
    # Terapkan rumus EAR
    EAR = (vert1 + vert2) / (2.0 * hor)
    return EAR


# Fungsi untuk menghitung Mouth Aspect Ratio (MAR)
def calculate_MAR(mar_pts, face):
    # Hitung jarak Euclidean antara landmark mulut vertikal
    vert1, _ = detector.findDistance(face[mar_pts[1]], face[mar_pts[7]])
    vert2, _ = detector.findDistance(face[mar_pts[2]], face[mar_pts[6]])
    vert3, _ = detector.findDistance(face[mar_pts[3]], face[mar_pts[5]])
    # Hitung jarak Euclidean antara landmark mulut horizontal
    hor, _ = detector.findDistance(face[mar_pts[0]], face[mar_pts[4]])
    # Terapkan rumus MAR
    MAR = (vert1 + vert2 + vert3) / (2.0 * hor)
    return MAR


# Fungsi untuk menampilkan peringatan visual di layar
def alert():
    # Pastikan 'img' bukan None sebelum menggambar
    if img is not None:
        cv2.rectangle(img, (0, img.shape[0] // 2 - 40), (img.shape[1], img.shape[0] // 2 + 40), (0, 0, 255), cv2.FILLED)
        text = "ANDA MENGANTUK!!!"
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_PLAIN, 3, 2)[0]
        text_x = (img.shape[1] - text_size[0]) // 2
        text_y = img.shape[0] // 2 + 20
        cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 2)
    else:
        print("Peringatan: Tidak dapat menampilkan peringatan visual karena 'img' adalah None.")


# Fungsi untuk merekam data deteksi ke file CSV
# recordData dipanggil saat kondisi berakhir, bukan saat dimulai/dikonfirmasi
def recordData(condition, start_time):
    with open("database.csv", "a", newline="") as file:
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        now = datetime.now()
        dtString = now.strftime("%d-%m-%Y %H:%M:%S")
        writer = csv.writer(file)
        writer.writerow((dtString, condition, f"{duration}s"))


# --- Fungsi untuk Mengirim Notifikasi Telegram ---
# Mengelola cooldown berdasarkan notification_type yang lebih spesifik
def send_telegram_notification(message, notification_type):
    global last_telegram_notification_time_motor_lvl1_down, last_telegram_notification_time_motor_lvl2_stop, last_telegram_notification_time_safety_face_missing
    current_time = time.time()

    # Tentukan jeda waktu berdasarkan jenis notifikasi
    if notification_type == "motor_lvl1_down":
        if (current_time - last_telegram_notification_time_motor_lvl1_down) < NOTIFICATION_COOLDOWN_SECONDS:
            return
    elif notification_type == "motor_lvl2_stop":
        if (current_time - last_telegram_notification_time_motor_lvl2_stop) < NOTIFICATION_COOLDOWN_SECONDS:
            return
    elif notification_type == "safety_face_missing":
        if (current_time - last_telegram_notification_time_safety_face_missing) < NOTIFICATION_COOLDOWN_SECONDS:
            return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()  # Mengeluarkan HTTPError untuk respons yang buruk (4xx atau 5xx)
        print(f"Notifikasi Telegram terkirim ({notification_type}): {message}")

        # Perbarui waktu notifikasi terakhir berdasarkan jenis
        if notification_type == "motor_lvl1_down":
            last_telegram_notification_time_motor_lvl1_down = current_time
        elif notification_type == "motor_lvl2_stop":
            last_telegram_notification_time_motor_lvl2_stop = current_time
        elif notification_type == "safety_face_missing":
            last_telegram_notification_time_safety_face_missing = current_time

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Gagal mengirim notifikasi Telegram: {e}")
        print("Pastikan koneksi internet stabil dan token/chat ID Telegram benar.")
    except Exception as e:
        print(f"ERROR: Terjadi kesalahan tak terduga saat mengirim notifikasi Telegram: {e}")


# --- Fungsi untuk Mengontrol Kecepatan Motor DC ---
def set_motor_speed(speed_value):
    global motor_speed_level
    if motor_pwm_pin_obj:  # Periksa apakah pin motor DC diinisialisasi
        try:
            # Nilai PWM pyfirmata berkisar antara 0.0 hingga 1.0, jadi bagi dengan 255.0
            motor_pwm_pin_obj.write(speed_value / 255.0)

            # Perbarui tingkat kecepatan motor DC dan cetak status
            if speed_value == SPEED_MAX_ADJUSTED:
                motor_speed_level = 2
                print(f"Motor DC diatur ke kecepatan NORMAL ({speed_value}).")
            elif speed_value == SPEED_HALF_ADJUSTED:
                motor_speed_level = 1
                print(f"Motor DC diatur ke kecepatan SETENGAH ({speed_value}).")
            elif speed_value == SPEED_STOP:
                motor_speed_level = 0
                print(f"Motor DC diatur ke kecepatan STOP ({speed_value}).")
        except Exception as e:
            print(f"ERROR: Gagal mengatur kecepatan motor DC: {e}")
            print("Pastikan koneksi Arduino stabil.")
    else:
        print("Arduino atau pin motor DC tidak terinisialisasi. Tidak dapat mengatur kecepatan.")


# --- Fungsi untuk Kalibrasi EAR ---
def calibrate_ear_threshold(num_frames=150, calibration_factor=0.80):  # Faktor 0.80
    print("\n--- MEMULAI KALIBRASI EAR ---")
    print("Harap jaga mata Anda tetap terbuka dan pandang kamera selama proses ini.")
    ear_values = []
    frames_calibrated = 0

    # Pastikan motor DC diatur ke kecepatan normal selama kalibrasi
    set_motor_speed(SPEED_MAX_ADJUSTED)

    while frames_calibrated < num_frames:
        success, img = cap.read()
        if not success:
            print("ERROR: Gagal membaca frame dari kamera saat kalibrasi. Menghentikan kalibrasi.")
            set_motor_speed(SPEED_STOP)  # Hentikan motor DC jika kamera gagal
            return None  # Keluar dari kalibrasi
        img = cv2.flip(img, 1)  # Balik gambar secara horizontal
        img, faces = detector.findFaceMesh(img, draw=False)  # Deteksi mesh wajah tanpa menggambar

        if faces:
            face = faces[0]  # Dapatkan wajah pertama yang terdeteksi
            left_EAR = calculate_EAR(left_eye_indices, face)
            right_EAR = calculate_EAR(right_eye_indices, face)
            avg_EAR = (left_EAR + right_EAR) / 2
            ear_values.append(avg_EAR)
            frames_calibrated += 1

            # Tampilkan pesan kalibrasi di layar
            calibration_text = f"Kalibrasi: Jaga Mata Terbuka ({frames_calibrated}/{num_frames})"
            cv2.putText(img, calibration_text, (50, 50), cv2.FONT_HERSHEY_PLAIN, 2, (0, 255, 0), 2)
            cv2.putText(img, f'EAR: {avg_EAR:.2f}', (50, 80), cv2.FONT_HERSHEY_PLAIN, 2, (0, 255, 0), 2)
        else:
            # Tampilkan pesan jika wajah tidak terdeteksi
            cv2.putText(img, "Wajah tidak terdeteksi. Posisikan wajah Anda di depan kamera.", (50, 50),
                        cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 255), 2)

        cv2.imshow("Sample", img)  # Tampilkan frame kalibrasi
        if cv2.waitKey(1) & 0xFF == ord('q'):  # Izinkan pengguna keluar dari kalibrasi
            print("Kalibrasi dibatalkan oleh pengguna.")
            set_motor_speed(SPEED_STOP)  # Hentikan motor DC jika kalibrasi dibatalkan
            return None

    if ear_values:
        avg_calibrated_ear = sum(ear_values) / len(ear_values)
        new_ear_thresh = avg_calibrated_ear * calibration_factor
        print(f"Kalibrasi selesai. Rata-rata EAR normal: {avg_calibrated_ear:.2f}")
        print(f"EAR_THRESH baru diatur ke: {new_ear_thresh:.2f}")
        set_motor_speed(
            SPEED_MAX_ADJUSTED)  # Kembalikan motor DC ke kecepatan normal yang disesuaikan setelah kalibrasi berhasil
        return new_ear_thresh
    else:
        print("Kalibrasi gagal: Tidak ada nilai EAR yang terekam. Pastikan wajah terdeteksi.")
        set_motor_speed(SPEED_STOP)  # Hentikan motor DC jika kalibrasi gagal
        return None


# --- Jalankan Kalibrasi EAR sebelum Loop Utama ---
# Pastikan kamera dan detektor sudah diinisialisasi sebelum memanggil kalibrasi
if cap.isOpened() and detector:
    calibrated_ear_thresh = calibrate_ear_threshold(num_frames=150, calibration_factor=0.80)
    if calibrated_ear_thresh is not None:
        EAR_THRESH = calibrated_ear_thresh
    else:
        print("Menggunakan EAR_THRESH default: 0.23 karena kalibrasi gagal.")
        EAR_THRESH = 0.23
else:
    print("Melewatkan kalibrasi EAR karena kamera atau detektor tidak siap.")
    EAR_THRESH = 0.23  # Gunakan nilai default jika kamera/detektor tidak siap

# --- Variabel Global untuk Kontrol Buzzer Dinamis ---
# 0: Mati, 1: Pola lambat (Lv1), 2: Pola cepat (Lv2)
buzzer_current_pattern_level = 0
buzzer_last_toggle_time = 0
buzzer_state_on = False  # Status fisik buzzer (True: ON, False: OFF)

# Durasi pola beep untuk setiap level
BEEP_ON_DURATION_LVL1 = 0.3  # Durasi ON untuk pola lambat (detik)
BEEP_OFF_DURATION_LVL1 = 0.7  # Durasi OFF untuk pola lambat (detik)

BEEP_ON_DURATION_LVL2 = 0.15  # Durasi ON untuk pola cepat (detik)
BEEP_OFF_DURATION_LVL2 = 0.15  # Durasi OFF untuk pola cepat (detik)


# Fungsi untuk mengelola pola beeping buzzer secara non-blocking
def handle_buzzer_beeping():
    global buzzer_last_toggle_time, buzzer_state_on, buzzer_current_pattern_level

    if buzzer_pin is None:  # Jika Arduino/buzzer tidak terinisialisasi
        return

    current_time = time.time()

    if buzzer_current_pattern_level == 0:  # Buzzer harus mati
        if buzzer_state_on:
            buzzer_pin.write(0)  # Pastikan buzzer OFF
            buzzer_state_on = False
        return

    # Tentukan durasi pola saat ini berdasarkan level
    if buzzer_current_pattern_level == 1:  # Pola lambat (Lv1)
        on_duration = BEEP_ON_DURATION_LVL1
        off_duration = BEEP_OFF_DURATION_LVL1
    elif buzzer_current_pattern_level == 2:  # Pola cepat (Lv2)
        on_duration = BEEP_ON_DURATION_LVL2
        off_duration = BEEP_OFF_DURATION_LVL2
    else:  # Fallback, seharusnya tidak terjadi jika level diatur dengan benar
        return

    # Logika untuk mengubah status buzzer
    if buzzer_state_on:  # Jika buzzer saat ini ON
        if (current_time - buzzer_last_toggle_time) >= on_duration:
            buzzer_pin.write(0)  # Matikan buzzer
            buzzer_state_on = False
            buzzer_last_toggle_time = current_time
    else:  # Jika buzzer saat ini OFF
        if (current_time - buzzer_last_toggle_time) >= off_duration:
            buzzer_pin.write(1)  # Nyalakan buzzer
            buzzer_state_on = True
            buzzer_last_toggle_time = current_time


# Loop Program Utama
try:  # Tambahkan blok try-except umum untuk loop utama untuk menangkap kesalahan tak terduga
    while True:
        success, img = cap.read()
        if not success:
            print("ERROR: Gagal membaca frame dari kamera dalam loop utama. Keluar.")
            # Jika kamera gagal, pastikan motor DC berhenti dan buzzer mati
            if board:
                set_motor_speed(SPEED_STOP)
                if buzzer_pin:
                    buzzer_pin.write(0)  # Pastikan buzzer mati
            break
        img = cv2.flip(img, 1)  # Balik gambar secara horizontal

        img, faces = detector.findFaceMesh(img, draw=False)  # Deteksi mesh wajah tanpa menggambar

        # --- Logika Kontrol Motor DC dan Pemulihan Kecepatan ---
        is_user_currently_drowsy_or_yawning = False  # Untuk menandakan apakah pengguna saat ini mengantuk/menguap
        face = None  # Inisialisasi 'face' ke None di setiap iterasi

        # Permintaan perubahan kecepatan untuk frame ini (-1: turun 1 level, 0: tidak ada perubahan)
        current_frame_speed_change_request = 0

        if faces:
            try:
                face = faces[0]  # Dapatkan wajah pertama jika terdeteksi
            except IndexError:
                print(
                    "PERINGATAN: Daftar 'faces' tidak kosong tetapi faces[0] menyebabkan IndexError. Melewatkan pemrosesan wajah.")
                face = None  # Pastikan 'face' adalah None jika ada masalah

        if face:  # Lanjutkan hanya jika 'face' berhasil didefinisikan
            # Hitung EAR dan MAR
            left_EAR = calculate_EAR(left_eye_indices, face)
            right_EAR = calculate_EAR(right_eye_indices, face)
            avg_EAR = (left_EAR + right_EAR) / 2
            mar = calculate_MAR(mar_points, face)

            # Periksa apakah pengguna menunjukkan tanda-tanda kantuk atau menguap (bahkan yang belum dikonfirmasi)
            if avg_EAR < EAR_THRESH or mar > MAR_THRESH:
                is_user_currently_drowsy_or_yawning = True

            # Logika deteksi kantuk (EAR)
            if avg_EAR < EAR_THRESH:
                if sleep_start_time is None:
                    sleep_start_time = time.time()
                breakcount_s += 1
                if breakcount_s >= EAR_CONSEC_FRAMES:
                    alert()  # Tampilkan peringatan visual
                    if not state_s:  # Ini adalah kejadian kantuk yang BARU terkonfirmasi
                        counter_s += 1
                        try:  # Coba putar suara
                            if sound:
                                sound.play()
                        except Exception as e:
                            print(f"ERROR: Gagal memutar suara alarm kantuk: {e}")

                        # recordData("Kantuk", sleep_start_time) # Pindahkan panggilan recordData

                        # Setel permintaan perubahan kecepatan jika belum ada
                        if current_frame_speed_change_request == 0:
                            current_frame_speed_change_request = -1  # Permintaan untuk turun 1 level
                        state_s = True  # Tandai kejadian kantuk sebagai aktif
            else:  # Kondisi kantuk berakhir
                breakcount_s = 0
                # Panggil recordData saat kondisi kantuk berakhir
                if state_s:  # Jika sebelumnya mengantuk, rekam durasi total
                    recordData("Kantuk", sleep_start_time)
                sleep_start_time = None
                if state_s:  # Jika sebelumnya mengantuk, matikan buzzer (akan ditangani oleh handle_buzzer_beeping)
                    pass
                state_s = False

            # Logika deteksi menguap (MAR)
            if mar > MAR_THRESH:
                if yawn_start_time is None:
                    yawn_start_time = time.time()
                breakcount_y += 1
                if breakcount_y >= MAR_CONSEC_FRAMES:
                    alert()  # Tampilkan peringatan visual
                    if not state_y:  # Ini adalah kejadian menguap yang BARU terkonfirmasi
                        counter_y += 1
                        try:  # Coba putar suara
                            if sound:
                                sound.play()
                        except Exception as e:
                            print(f"ERROR: Gagal memutar suara alarm menguap: {e}")

                        # recordData("Menguap", yawn_start_time) # Pindahkan panggilan recordData

                        # Setel permintaan perubahan kecepatan jika belum ada
                        if current_frame_speed_change_request == 0:
                            current_frame_speed_change_request = -1  # Permintaan untuk turun 1 level
                        state_y = True  # Tandai kejadian menguap sebagai aktif
            else:  # Kondisi menguap berakhir
                breakcount_y = 0
                # Panggil recordData saat kondisi menguap berakhir
                if state_y:  # Jika sebelumnya menguap, rekam durasi total
                    recordData("Menguap", yawn_start_time)
                yawn_start_time = None
                if state_y:  # Jika sebelumnya menguap, matikan buzzer (akan ditangani oleh handle_buzzer_beeping)
                    pass
                state_y = False

            # --- KONTROL KECEPATAN MOTOR DC KONSOLIDASI ---
            # Ini memastikan hanya SATU perubahan kecepatan terjadi per frame
            if current_frame_speed_change_request == -1:  # Ada permintaan penurunan kecepatan
                if motor_speed_level == 2:  # Dari kecepatan normal ke setengah
                    set_motor_speed(SPEED_HALF_ADJUSTED)
                    # Atur pola buzzer ke level 1 (lambat)
                    buzzer_current_pattern_level = 1
                    send_telegram_notification(
                        f"⚠️ Peringatan Kantuk/Menguap Lv1: Mobil Melambat pada {datetime.now().strftime('%H:%M:%S')}!",
                        "motor_lvl1_down")  # Menggunakan tipe notifikasi baru
                elif motor_speed_level == 1:  # Dari setengah kecepatan ke berhenti
                    set_motor_speed(SPEED_STOP)
                    # Atur pola buzzer ke level 2 (cepat)
                    buzzer_current_pattern_level = 2
                    send_telegram_notification(
                        f"❗ Peringatan Kantuk/Menguap Lv2: Mobil Berhenti pada {datetime.now().strftime('%H:%M:%S')}!",
                        "motor_lvl2_stop")  # Menggunakan tipe notifikasi baru
            # -----------------------------------------------

            # --- Logika Pemulihan Kecepatan Motor DC ---
            # Pulihkan hanya jika tidak ada tanda-tanda kantuk atau menguap yang saat ini ada (bahkan yang belum dikonfirmasi)
            # DAN tidak ada permintaan penurunan kecepatan di frame ini
            if not is_user_currently_drowsy_or_yawning and current_frame_speed_change_request == 0:
                if not recovery_timer_active:
                    recovery_timer_active = True
                    recovery_start_time = time.time()  # Mulai pengatur waktu pemulihan

                elapsed_recovery_time = time.time() - recovery_start_time

                if motor_speed_level == 0:  # Jika motor DC berhenti, coba pulih ke setengah kecepatan
                    if elapsed_recovery_time >= RECOVERY_DELAY_STOP_TO_HALF:
                        set_motor_speed(SPEED_HALF_ADJUSTED)
                        # Atur pola buzzer ke level 1 (lambat) saat pulih ke setengah
                        buzzer_current_pattern_level = 1
                        # Reset pengatur waktu untuk tahap pemulihan selanjutnya
                        recovery_start_time = time.time()
                elif motor_speed_level == 1:  # Jika motor DC setengah kecepatan, coba pulih ke kecepatan maksimal
                    if elapsed_recovery_time >= RECOVERY_DELAY_HALF_TO_MAX:
                        set_motor_speed(SPEED_MAX_ADJUSTED)
                        # Matikan pola buzzer saat pulih ke normal
                        buzzer_current_pattern_level = 0
                        recovery_timer_active = False  # Pemulihan selesai
                        recovery_start_time = 0
            else:  # Pengguna menunjukkan tanda-tanda kantuk atau menguap, reset pengatur waktu pemulihan
                recovery_timer_active = False
                recovery_start_time = 0

            # Warna indikator status
            status_color = (0, 255, 0)  # Default: hijau (aman)
            if avg_EAR < EAR_THRESH or mar > MAR_THRESH:  # Jika ada tanda-tanda awal
                status_color = (0, 255, 255)  # Kuning: mulai merasa kantuk/menguap
            if breakcount_s >= EAR_CONSEC_FRAMES or breakcount_y >= MAR_CONSEC_FRAMES:
                status_color = (0, 0, 255)  # Merah: alarm aktif (terkonfirmasi)

            # Tampilkan nilai EAR & MAR di layar
            cv2.putText(img, f'EAR: {avg_EAR:.2f}', (10, 30), cv2.FONT_HERSHEY_PLAIN, 2, status_color, 2)
            cv2.putText(img, f'MAR: {mar:.2f}', (10, 60), cv2.FONT_HERSHEY_PLAIN, 2, status_color, 2)

            # Tampilkan penghitung di layar
            cv2.putText(img, f'Jumlah Kantuk: {counter_s}', (10, img.shape[0] - 60), cv2.FONT_HERSHEY_PLAIN, 2,
                        (255, 255, 255), 2)
            cv2.putText(img, f'Jumlah Menguap: {counter_y}', (10, img.shape[0] - 30), cv2.FONT_HERSHEY_PLAIN, 2,
                        (255, 255, 255), 2)
            # Tampilkan status motor DC di layar
            motor_status_text = ""
            if motor_speed_level == 2:
                motor_status_text = "Status Mobil: MELAJU (Normal)"
            elif motor_speed_level == 1:
                motor_status_text = "Status Mobil: MELAMBAT (Kantuk Lv1)"
            elif motor_speed_level == 0:
                motor_status_text = "Status Mobil: BERHENTI (Kantuk Lv2)"

            cv2.putText(img, motor_status_text, (10, img.shape[0] - 90), cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 0), 2)

            # Gambar landmark FaceMesh di layar
            for id in faceId:
                cv2.circle(img, face[id], 3, status_color, cv2.FILLED)

        else:  # Jika wajah tidak terdeteksi ('face' adalah None)
            # Untuk keamanan, hentikan motor DC jika wajah tidak terdeteksi
            if motor_speed_level != 0:  # Hanya jika motor DC belum berhenti
                set_motor_speed(SPEED_STOP)
                # Atur pola buzzer ke level 2 (cepat) saat mobil berhenti karena wajah hilang
                buzzer_current_pattern_level = 2
                send_telegram_notification(
                    f"⚠️ Peringatan: Wajah Tidak Terdeteksi! Mobil Berhenti pada {datetime.now().strftime('%H:%M:%S')}!",
                    "safety_face_missing")  # Menggunakan tipe notifikasi baru

            # Reset semua penghitung dan pengatur waktu jika wajah tidak terdeteksi
            breakcount_s, breakcount_y = 0, 0
            state_s, state_y = False, False
            sleep_start_time = None
            yawn_start_time = None
            recovery_timer_active = False
            recovery_start_time = 0

            # Tampilkan pesan "Wajah Tidak Terdeteksi" di layar
            cv2.putText(img, "Wajah Tidak Terdeteksi!", (img.shape[1] // 2 - 150 + 5, img.shape[0] // 2 - 20),
                        cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 255), 3)
            cv2.putText(img, "Posisikan Diri Anda di Depan Kamera.",
                        (img.shape[1] // 2 - 250 + 3, img.shape[0] // 2 + 30),
                        cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 255), 2)

        cv2.imshow("Sample", img)  # Tampilkan frame yang diproses
        if cv2.waitKey(1) & 0xFF == ord('q'):  # Tekan 'q' untuk keluar
            print("Tombol 'q' ditekan. Keluar dari program.")
            break

        # --- Panggil fungsi pengelola buzzer di setiap frame ---
        handle_buzzer_beeping()

except Exception as main_loop_e:
    print(f"\n!!! TERJADI KESALAHAN KRITIS DALAM LOOP UTAMA !!!")
    print(f"Error: {main_loop_e}")
    import traceback

    traceback.print_exc()  # Cetak traceback lengkap untuk informasi error detail

finally:  # Pastikan sumber daya dibersihkan bahkan jika terjadi kesalahan
    print("\nMembersihkan sumber daya...")
    if cap.isOpened():  # Pastikan 'cap' dibuka sebelum dilepaskan
        cap.release()
        print("Kamera dilepaskan.")
    cv2.destroyAllWindows()
    print("Jendela OpenCV ditutup.")
    if board:  # Pastikan 'board' diinisialisasi sebelum menutupnya
        set_motor_speed(SPEED_STOP)  # Pastikan motor DC mati saat program berakhir
        # Pastikan buzzer mati saat program berakhir
        if buzzer_pin:
            try:
                buzzer_pin.write(0)
            except Exception as e:
                print(f"ERROR: Gagal mematikan buzzer saat keluar: {e}")
        try:
            board.exit()  # Tutup koneksi Arduino
            print("Koneksi Arduino ditutup.")
        except Exception as arduino_exit_e:
            print(f"ERROR: Gagal menutup koneksi Arduino: {e}")
    print("Program selesai.")
