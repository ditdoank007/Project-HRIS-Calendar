# HRIS Calendar — Notification Center V1

## Final Business Rules

### Bell / Badge
- Bell berada di header kanan atas, di sebelah nama pegawai.
- Badge hanya menghitung notification UNREAD + ACTIVE milik NIP login.
- Polling ringan setiap 45 detik.
- Klik bell membuka dropdown.
- Klik notification menandai READ, mengurangi badge, menghapus item dari dropdown, lalu membuka event terkait.
- READ dan COMPLETED adalah status berbeda.
- Record notification tidak dihapus; hanya tidak ditampilkan lagi setelah READ/COMPLETED.

### 1. Dinas Luar
Trigger:
- Operator memasukkan pegawai ke dalam SPRIN.

Recipient:
- Pegawai yang tercantum dalam SPRIN.

Behavior:
- Notification muncul saat assignment SPRIN dibuat.
- Tidak membuat duplicate untuk NIP + SPRIN yang sama.
- Jika SPRIN diedit dan pegawai dihapus, notification aktif pegawai tersebut dinonaktifkan.
- Jika pegawai baru ditambahkan, notification baru dibuat.
- Notification otomatis expired setelah periode Dinas Luar terakhir untuk SPRIN tersebut lewat.

### 2. Agenda Rapat
Trigger:
- Operator membuat Agenda Rapat.

Recipient:
- Semua pegawai aktif, mengikuti rule kalender pribadi yang saat ini menampilkan agenda TERJADWAL.

Behavior:
- Notification hanya dibuat saat agenda pertama dibuat.
- Scan QR tidak membuat notification baru.
- Selama status TERJADWAL, agenda tetap muncul di kalender pribadi.
- Saat operator menekan RAPAT SELESAI:
  - Pegawai yang HADIR melalui QR tetap mendapatkan rapat di kalender pribadi.
  - Pegawai yang tidak hadir kehilangan agenda dari kalender pribadi.
  - Notification rapat dinonaktifkan untuk semua recipient.
- Jika rapat BATAL, notification juga dinonaktifkan.

### 3. Kesamaptaan
Trigger:
- Operator membuat agenda Kesamaptaan.

Recipient:
- Semua pegawai aktif.

Behavior:
- Agenda TERJADWAL muncul di kalender pribadi semua pegawai.
- Notification muncul satu kali saat agenda dibuat.
- Scan QR tidak membuat notification baru.
- Saat operator menekan SELESAI:
  - Pegawai yang HADIR melalui QR tetap mendapatkan Kesamaptaan di kalender pribadi.
  - Pegawai yang tidak hadir kehilangan agenda dari kalender pribadi.
  - Notification dinonaktifkan untuk semua recipient.
- Jika kegiatan BATAL, notification dinonaktifkan.

### 4. Disposisi
Trigger:
- Operator membuat Disposisi dan menetapkan pegawai.

Recipient:
- NIP yang tercantum pada AGENDA_DISPOSISI_PESERTA.

Behavior:
- Notification dibuat saat pegawai ditugaskan.
- Tidak duplicate untuk NIP + AGENDA_ID.
- Notification hilang dari dropdown setelah dibuka.
- Jika disposisi dibatalkan, notification dinonaktifkan.

## Data / Security
Notification menggunakan tabel existing CALENDAR_NOTIFICATION yang dikembangkan dengan source metadata.

Identitas logical notification:
NIP + SOURCE_TYPE + SOURCE_ID

Source:
- AGENDA_RAPAT
- DISPOSISI
- KESAMAPTAAN
- DINAS_LUAR

API selalu menggunakan session NIP pada Calendar atau X-Calendar-NIP + X-Calendar-Internal-Key pada internal HRIS API.

Pegawai tidak boleh membaca atau menandai notification milik NIP lain.

## Database
Migration:
development/schema_usecase/sql/calendar_notification_v1.sql

Migration memperluas CALENDAR_NOTIFICATION dan memetakan notification Agenda Rapat lama. Notification lama untuk event yang sudah SELESAI/BATAL dinonaktifkan saat migration.

## V1 Definition of Done
- [x] Bell icon.
- [x] Unread badge.
- [x] Dropdown notification.
- [x] Mark as read.
- [x] Read-all.
- [x] Polling 45 detik.
- [x] Agenda Rapat.
- [x] Kesamaptaan.
- [x] Disposisi.
- [x] Dinas Luar.
- [x] Deduplication.
- [x] Ownership validation.
- [x] Event completion lifecycle.
- [x] Responsive desktop/mobile.
