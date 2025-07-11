# Sistem Deteksi Kantuk dan Menguap dengan Kontrol Motor DC

Proyek ini adalah sistem berbasis visi komputer yang dirancang untuk mendeteksi tanda-tanda kantuk (mengantuk) dan menguap pada pengguna secara *real-time*. Ketika kondisi kantuk terdeteksi, sistem akan memicu serangkaian peringatan (visual, suara, *buzzer*) dan secara bertahap mengurangi kecepatan simulasi motor DC (mewakili pergerakan mobil). Sistem ini juga dilengkapi dengan notifikasi Telegram dan perekaman data.

## Daftar Isi

* [Fitur Utama](#fitur-utama)
* [Cara Kerja Sistem](#cara-kerja-sistem)
    * [Deteksi Kantuk (Eye Aspect Ratio - EAR)](#deteksi-kantuk-eye-aspect-ratio---ear)
    * [Deteksi Menguap (Mouth Aspect Ratio - MAR)](#deteksi-menguap-mouth-aspect-ratio---mar)
    * [Kontrol Motor DC Progresif](#kontrol-motor-dc-progresif)
    * [Pemulihan Kecepatan Motor DC Bertahap](#pemulihan-kecepatan-motor-dc-bertahap)
    * [Peringatan Multi-Saluran](#peringatan-multi-saluran)
    * [Perekaman Data](#perekaman-data)
    * [Penanganan Wajah Tidak Terdeteksi](#penanganan-wajah-tidak-terdeteksi)
* [Persyaratan Sistem](#persyaratan-sistem)
* [Instalasi](#instalasi)
    * [1. Persiapan Lingkungan Python](#1-persiapan-lingkungan-python)
    * [2. Persiapan Arduino](#2-persiapan-arduino)
    * [3. Konfigurasi Telegram Bot](#3-konfigurasi-telegram-bot)
* [Koneksi Hardware](#koneksi-hardware)
    * [1. Arduino Uno](#1-arduino-uno)
    * [2. L298N Motor Driver](#2-l298n-motor-driver)
    * [3. Motor DC](#3-motor-dc)
    * [4. Buzzer](#4-buzzer)
    * [5. Sumber Daya Eksternal](#5-sumber-daya-eksternal)
* [Konfigurasi Program](#konfigurasi-program)
* [Cara Menjalankan](#cara-menjalankan)
* [Debugging dan Pemecahan Masalah](#debugging-dan-pemecahan-masalah)
* [Kontribusi](#kontribusi)
* [Lisensi](#lisensi)

## Fitur Utama

* **Deteksi Kantuk & Menguap Real-time**: Menggunakan kamera dan teknik visi komputer untuk memantau mata (EAR) dan mulut (MAR).
* **Kalibrasi EAR Otomatis**: Menyesuaikan ambang batas deteksi kantuk secara personal untuk akurasi yang lebih baik.
* **Kontrol Motor DC Progresif**: Mensimulasikan pergerakan mobil dengan menurunkan kecepatan motor DC secara bertahap saat kantuk/menguap terdeteksi, dan menghentikannya pada tingkat kantuk ekstrem.
* **Pemulihan Kecepatan Bertahap**: Motor DC akan pulih kecepatannya secara bertahap saat pengguna kembali ke kondisi aman.
* **Peringatan Multi-Saluran**: Memberikan *feedback* melalui:
    * **Visual**: Pesan di layar dan perubahan warna indikator.
    * **Audio**: Suara alarm.
    * **Fisik**: Buzzer yang terhubung ke Arduino dengan pola suara berbeda per level.
    * **Notifikasi Telegram**: Peringatan instan ke ponsel.
* **Perekaman Data**: Mencatat durasi setiap kejadian kantuk/menguap ke file CSV.
* **Penanganan Wajah Tidak Terdeteksi**: Menghentikan motor DC dan memberikan peringatan jika wajah tidak terdeteksi di kamera.
* **Robustness**: Dilengkapi dengan penanganan kesalahan yang komprehensif untuk stabilitas program.

## Cara Kerja Sistem

Sistem ini bekerja dengan menganalisis *frame* video dari kamera secara terus-menerus.

### Deteksi Kantuk (Eye Aspect Ratio - EAR)

* **Konsep**: EAR mengukur seberapa terbuka mata. Nilainya akan menurun saat mata tertutup.
* **Kalibrasi**: Saat program dimulai, Anda diminta untuk menjaga mata tetap terbuka. Sistem mengukur rata-rata EAR normal Anda.
* **Ambang Batas (`EAR_THRESH`)**: Dihitung sebagai `rata-rata EAR normal * 0.80`. Jika `avg_EAR` turun di bawah ambang batas ini, potensi kantuk terdeteksi.
* **Konfirmasi**: Kondisi mata tertutup harus berlangsung selama `40` *frame* berturut-turut (`EAR_CONSEC_FRAMES`) untuk dikonfirmasi sebagai kantuk.

### Deteksi Menguap (Mouth Aspect Ratio - MAR)

* **Konsep**: MAR mengukur seberapa terbuka mulut. Nilainya akan meningkat saat mulut terbuka lebar (menguap).
* **Ambang Batas (`MAR_THRESH`)**: Ditetapkan pada `0.65`. Jika `mar` melebihi nilai ini, potensi menguap terdeteksi.
* **Konfirmasi**: Kondisi mulut terbuka harus berlangsung selama `40` *frame* berturut-turut (`MAR_CONSEC_FRAMES`) untuk dikonfirmasi sebagai menguap.

### Kontrol Motor DC Progresif

Sistem mengontrol kecepatan motor DC (simulasi mobil) berdasarkan tingkat kantuk/menguap yang terkonfirmasi. Logika ini dikonsolidasikan untuk memastikan hanya satu perubahan kecepatan terjadi per *frame* meskipun beberapa indikasi terdeteksi bersamaan.

* **Kecepatan Normal (`SPEED_MAX_ADJUSTED = 254`)**: Motor DC berjalan pada kecepatan penuh yang disesuaikan saat tidak ada deteksi kantuk/menguap.
* **Kantuk/Menguap Level 1 (`SPEED_HALF_ADJUSTED = 127`)**: Jika kantuk atau menguap terkonfirmasi saat motor dalam kecepatan normal, kecepatan motor akan diturunkan menjadi setengah. Buzzer akan berbunyi dengan pola "bip bip" jarang.
* **Kantuk/Menguap Level 2 (`SPEED_STOP = 0`)**: Jika kantuk atau menguap terkonfirmasi lagi saat motor sudah dalam kecepatan setengah, motor akan dihentikan sepenuhnya. Buzzer akan berbunyi dengan pola "bip bip" lebih sering/terus-menerus.

### Pemulihan Kecepatan Motor DC Bertahap

Ketika pengguna kembali ke kondisi aman (tidak mengantuk dan tidak menguap) untuk durasi tertentu:

* **Dari Berhenti ke Setengah**: Motor akan pulih ke kecepatan setengah (`SPEED_HALF_ADJUSTED`) setelah `5` detik (`RECOVERY_DELAY_STOP_TO_HALF`) berada dalam kondisi aman. Buzzer akan kembali ke pola "bip bip" jarang.
* **Dari Setengah ke Normal**: Motor akan pulih ke kecepatan normal (`SPEED_MAX_ADJUSTED`) setelah `5` detik (`RECOVERY_DELAY_HALF_TO_MAX`) lagi berada dalam kondisi aman. Buzzer akan mati.

### Peringatan Multi-Saluran

* **Layar**: Menampilkan pesan "ANDA MENGANTUK!!!" dan mengubah warna indikator status (Hijau: Aman, Kuning: Awal Kantuk/Menguap, Merah: Alarm Aktif).
* **Suara**: Memutar file `alarm.wav`.
* **Buzzer**: Mengeluarkan pola suara "bip bip" yang berbeda (jarang untuk Level 1, sering untuk Level 2) melalui Arduino. Kontrol buzzer bersifat non-blocking, memastikan kelancaran program.
* **Telegram**: Mengirim notifikasi ke ponsel Anda dengan pesan spesifik untuk setiap level kantuk/menguap atau saat wajah tidak terdeteksi. Notifikasi memiliki *cooldown* `60` detik (`NOTIFICATION_COOLDOWN_SECONDS`) untuk mencegah *spam*. Jenis notifikasi yang dikirim meliputi: `motor_lvl1_down`, `motor_lvl2_stop`, dan `safety_face_missing`.

### Perekaman Data

Setiap kejadian kantuk atau menguap akan dicatat ke file `database.csv` dengan format:
`Tanggal-Waktu, Kondisi (Kantuk/Menguap), Durasi (dalam detik)`
Durasi dihitung dari awal terdeteksinya kondisi hingga kondisi tersebut berakhir.

### Penanganan Wajah Tidak Terdeteksi

Jika wajah pengguna tidak terdeteksi di kamera:

* Motor DC akan segera berhenti (`SPEED_STOP`).
* Buzzer akan berbunyi dengan pola cepat (Level 2).
* Notifikasi Telegram akan dikirim ("Wajah Tidak Terdeteksi! Mobil Berhenti").
* Semua penghitung dan pengatur waktu akan direset.
* Pesan visual "Wajah Tidak Terdeteksi!" akan ditampilkan di layar, diratakan tengah secara visual.

## Persyaratan Sistem

* Sistem Operasi: Windows, macOS, atau Linux
* Python 3.x
* Webcam
* Arduino Uno (atau kompatibel)
* Modul Driver Motor L298N
* Motor DC
* Buzzer (pasif atau aktif)
* Kabel Jumper
* Sumber Daya Eksternal untuk L298N (misalnya, adaptor 9V/12V atau baterai)
* Koneksi Internet (untuk notifikasi Telegram)

## Instalasi

### 1. Persiapan Lingkungan Python

1.  **Instal Python**: Pastikan Python 3.x terinstal di sistem Anda.
2.  **Buat Lingkungan Virtual (Direkomendasikan)**:
    ```bash
    python -m venv venv
    # Aktifkan lingkungan virtual
    # Windows: .\venv\Scripts\activate
    # macOS/Linux: source venv/bin/activate
    ```
3.  **Instal Pustaka Python**:
    ```bash
    pip install opencv-python mediapipe cvzone pyglet pyfirmata requests
    ```
    * `opencv-python`: Untuk pemrosesan gambar dan kamera.
    * `mediapipe`: Digunakan oleh `cvzone` untuk deteksi FaceMesh.
    * `cvzone`: Pustaka yang menyederhanakan penggunaan MediaPipe.
    * `pyglet`: Untuk memutar suara alarm.
    * `pyfirmata`: Untuk komunikasi dengan Arduino.
    * `requests`: Untuk mengirim notifikasi ke Telegram API.

### 2. Persiapan Arduino

1.  **Instal Arduino IDE**: Unduh dan instal Arduino IDE dari [situs resmi Arduino](https://www.arduino.cc/en/software).
2.  **Hubungkan Arduino**: Sambungkan Arduino Uno Anda ke komputer menggunakan kabel USB.
3.  **Pilih Papan dan Port**: Di Arduino IDE, buka `Tools > Board` dan pilih papan Arduino Anda (misal: `Arduino Uno`). Kemudian, buka `Tools > Port` dan pilih port COM yang sesuai dengan Arduino Anda.
4.  **Upload StandardFirmata**:
    * Buka *sketch* `StandardFirmata`: `File > Examples > Firmata > StandardFirmata`.
    * Klik tombol **Upload** (panah ke kanan) untuk mengunggah *sketch* ini ke Arduino Anda.
    * **Penting**: Setelah *upload*, **tutup Serial Monitor** di Arduino IDE jika terbuka. Serial Monitor akan mengunci port dan mencegah program Python terhubung.

### 3. Konfigurasi Telegram Bot

1.  **Buat Bot Telegram**:
    * Buka aplikasi Telegram Anda dan cari **@BotFather**.
    * Ketik `/start` lalu `/newbot`. Ikuti instruksi untuk memberi nama dan *username* bot Anda.
    * Setelah berhasil, @BotFather akan memberikan Anda **HTTP API Token**. Salin token ini.
2.  **Dapatkan Chat ID Anda**:
    * Cari *username* bot Anda di Telegram dan kirim pesan apa saja (misal: `/start`).
    * Buka *browser* web Anda dan kunjungi URL berikut (ganti `YOUR_BOT_TOKEN` dengan token bot Anda):
        `https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates`
    * Di *output* JSON yang muncul, cari bagian `"chat"` dan di dalamnya, temukan nilai `"id"`. Ini adalah **Chat ID** Anda.
3.  **Perbarui Kode Python**: Buka file `main.py` (atau nama file kode Anda) dan perbarui bagian konfigurasi Telegram:
    ```python
    TELEGRAM_BOT_TOKEN = 'PASTE_TOKEN_ANDA_DI_SINI'
    TELEGRAM_CHAT_ID = 'PASTE_CHAT_ID_ANDA_DI_SINI'
    ```

## Koneksi Hardware

Pastikan semua komponen terhubung dengan benar seperti yang dijelaskan di bawah ini.

### 1. Arduino Uno

| Pin Arduino | Terhubung ke | Fungsi |
| :---------- | :----------- | :----- |
| **Digital 7** | Kaki Positif (+) Buzzer | Mengaktifkan/menonaktifkan buzzer. |
| **Digital 9 (PWM)** | Pin `ENA` pada L298N | Mengontrol kecepatan motor DC A. |
| **Digital 10** | Pin `IN1` pada L298N | Mengontrol arah putaran motor DC A (bersama IN2). |
| **Digital 11** | Pin `IN2` pada L298N | Mengontrol arah putaran motor DC A (bersama IN1). |
| **`GND` (Ground)** | Pin `GND` pada L298N <br> Terminal negatif (-) Sumber Daya Eksternal | Menyediakan *common ground* untuk seluruh sirkuit. **Sangat Penting!** |
| **`5V`** | Pin `5V` (atau `VSS`) pada L298N (jika jumper `5V Enable` dilepas) | Memberikan daya 5V untuk sirkuit logika L298N. |
| **USB Port** | Komputer (PC) | Memberikan daya ke Arduino dan komunikasi serial dengan program Python. |

### 2. L298N Motor Driver

| Pin L298N | Terhubung ke | Fungsi |
| :-------- | :----------- | :----- |
| **`+12V` (atau `VS`)** | Terminal positif (+) Sumber Daya Eksternal | Input daya utama untuk motor DC. |
| **`GND`** | Pin `GND` pada Arduino <br> Terminal negatif (-) Sumber Daya Eksternal | *Common ground* untuk modul dan motor. |
| **`5V` (atau `VSS`)** | Pin `5V` pada Arduino (jika jumper `5V Enable` dilepas) <br> **Atau dibiarkan kosong** (jika jumper terpasang & VS > 7V) | Memberikan daya 5V untuk logika internal L298N. |
| **`ENA`** | Pin Digital 9 (PWM) pada Arduino | Mengontrol kecepatan Motor A. |
| **`IN1`** | Pin Digital 10 pada Arduino | Mengontrol arah Motor A. |
| **`IN2`** | Pin Digital 11 pada Arduino | Mengontrol arah Motor A. |
| **`OUT1` & `OUT2`** | Dua terminal Motor DC Anda | Output daya yang dikontrol ke Motor DC A. |
| **`ENB`, `IN3`, `IN4`, `OUT3`, `OUT4`** | (Tidak digunakan dalam proyek ini) | Pin untuk mengontrol Motor B. |

### 3. Motor DC

| Terminal Motor DC | Terhubung ke | Fungsi |
| :---------------- | :----------- | :----- |
| **Terminal 1** | Pin `OUT1` L298N | Menerima daya terkontrol dari L298N. |
| **Terminal 2** | Pin `OUT2` L298N | Menerima daya terkontrol dari L298N. |

### 4. Buzzer

| Terminal Buzzer | Terhubung ke | Fungsi |
| :-------------- | :----------- | :----- |
| **Positif (+)** | Pin Digital 7 Arduino | Menerima sinyal kontrol dari Arduino. |
| **Negatif (-)** | Pin `GND` Arduino | Melengkapi sirkuit buzzer. |

### 5. Sumber Daya Eksternal

* **Terminal Positif (+)**: Terhubung ke pin **`+12V` (atau `VS`) pada L298N**.
* **Terminal Negatif (-)**: Terhubung ke pin **`GND` pada L298N** (dan secara tidak langsung ke `GND` Arduino).

## Konfigurasi Program

Sebelum menjalankan program, Anda dapat menyesuaikan beberapa parameter di bagian awal kode (`main.py`):

* **`TELEGRAM_BOT_TOKEN`**: Token API bot Telegram Anda.
* **`TELEGRAM_CHAT_ID`**: ID chat Telegram Anda.
* **`NOTIFICATION_COOLDOWN_SECONDS`**: Jeda waktu antar notifikasi Telegram (default: 60 detik).
* **`MOTOR_PWM_PIN`, `MOTOR_IN1_PIN`, `MOTOR_IN2_PIN`**: Pin Arduino yang terhubung ke L298N.
* **`SPEED_MAX_ADJUSTED`, `SPEED_HALF_ADJUSTED`, `SPEED_STOP`**: Tingkat kecepatan PWM untuk motor DC (saat ini 254, 127, 0).
* **`RECOVERY_DELAY_STOP_TO_HALF`, `RECOVERY_DELAY_HALF_TO_MAX`**: Durasi pemulihan kecepatan motor DC (default: 5 detik).
* **`arduino_port`**: Port COM Arduino Anda (misal: "COM5" di Windows).
* **`arduino_buzzer_pin_num`**: Pin digital Arduino untuk buzzer (default: 7).
* **`EAR_CONSEC_FRAMES`, `MAR_CONSEC_FRAMES`**: Jumlah *frame* berturut-turut untuk konfirmasi deteksi (default: 40).
* **`MAR_THRESH`**: Ambang batas MAR untuk deteksi menguap (default: 0.65).
* **`calibration_factor`**: Faktor sensitivitas kalibrasi EAR (default: 0.80).
* **`BEEP_ON_DURATION_LVL1/2`, `BEEP_OFF_DURATION_LVL1/2`**: Durasi pola suara buzzer untuk setiap level.

## Cara Menjalankan

1.  Pastikan semua langkah [Instalasi](#instalasi) dan [Koneksi Hardware](#koneksi-hardware) telah diselesaikan dengan benar.
2.  Buka terminal atau *command prompt* Anda.
3.  Navigasikan ke direktori tempat Anda menyimpan file `main.py` (atau nama file kode Anda).
4.  Aktifkan lingkungan virtual Python Anda (jika Anda membuatnya).
5.  Jalankan skrip Python:
    ```bash
    python main.py
    ```
6.  Program akan memulai kalibrasi EAR. Ikuti instruksi di layar untuk menjaga mata tetap terbuka dan pandang kamera.
7.  Setelah kalibrasi selesai, sistem akan mulai memantau Anda secara *real-time*.

## Debugging dan Pemecahan Masalah

* **Kamera tidak terbuka**: Pastikan kamera tidak sedang digunakan oleh aplikasi lain. Coba *restart* program atau komputer. Periksa apakah `cap = cv2.VideoCapture(0)` menggunakan indeks kamera yang benar (coba 1, 2, dst. jika 0 tidak berhasil).
* **Arduino tidak terhubung / Motor DC tidak bergerak / Buzzer tidak berbunyi**:
    * Pastikan *sketch* `StandardFirmata` sudah di-*upload* ke Arduino dan **Serial Monitor di Arduino IDE ditutup**.
    * Verifikasi `arduino_port` di kode Python cocok dengan port COM Arduino Anda.
    * Periksa semua koneksi kabel pada Arduino, L298N, motor DC, dan buzzer. Pastikan tidak ada kabel longgar.
    * Pastikan L298N memiliki **sumber daya eksternal** yang cukup dan terhubung dengan benar ke pin `+12V` dan `GND` L298N.
    * Perhatikan pesan `ERROR` di konsol PyCharm Anda.
* **Notifikasi Telegram tidak terkirim**:
    * Pastikan `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` sudah benar di kode Anda.
    * Pastikan komputer Anda memiliki koneksi internet aktif.
    * Periksa konsol PyCharm untuk pesan `ERROR` terkait pengiriman Telegram.
* **Deteksi kantuk/menguap terlalu sensitif/tidak sensitif**:
    * Sesuaikan `calibration_factor` di fungsi `calibrate_ear_threshold()` (`0.80` adalah nilai awal, coba nilai yang lebih rendah seperti `0.70` atau `0.65` untuk deteksi kantuk yang lebih sensitif).
    * Sesuaikan `EAR_CONSEC_FRAMES` atau `MAR_CONSEC_FRAMES` (jumlah *frame* berturut-turut yang diperlukan). Menurunkan nilai ini akan membuat deteksi lebih cepat tanggap.
* **Motor DC bergerak terlalu pelan saat start**: Ini sudah diatasi dengan `time.sleep(1)` setelah `it.start()`. Jika masih terjadi, coba sesuaikan `SPEED_MAX_ADJUSTED` menjadi `250` atau nilai lain yang sedikit di bawah `255` untuk memastikan sinyal PWM optimal.

## Kontribusi

Kontribusi sangat diterima! Jika Anda memiliki ide untuk perbaikan atau fitur baru, jangan ragu untuk membuka *issue* atau mengirimkan *pull request*.

