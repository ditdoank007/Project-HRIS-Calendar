# Global UI Standard — QR Scan & Registration Flow

**Project:** HRIS Calendar Kantor SAR Surabaya  
**Branch:** `feature/pengajuanku-sidebar`  
**Status:** STANDARD / SOURCE OF TRUTH

## 1. Tujuan

Semua alur yang dibuka melalui QR Code publik di Calendar harus menggunakan pola UI dan alur yang konsisten.

Berlaku untuk:
- Rekam Medis
- Agenda / Rapat
- Kehadiran kegiatan
- Form pendaftaran peserta
- Alur QR publik lain yang membutuhkan identifikasi atau pendaftaran

## 2. Prinsip Utama

Setelah pengguna menekan tombol **Daftar / Simpan / Simpan Kehadiran**, form **tidak boleh tetap tampil dalam keadaan disabled**.

Form harus digantikan oleh **Success State**.

Success State minimal berisi:

1. Ikon sukses
2. Judul: **Pendaftaran Berhasil**
3. Pesan: **Pendaftaran Anda berhasil.**
4. Informasi singkat kegiatan/agenda
5. Pesan tindak lanjut sesuai konteks, misalnya:
   - **Silahkan menunggu antrian untuk pemeriksaan Rekam Medis.**
   - **Silahkan menunggu antrian / proses kehadiran agenda.**

Tidak boleh meninggalkan field form di halaman setelah pendaftaran berhasil.

## 3. QR Rekam Medis

### Pegawai

Alur:

`Scan QR`
→ Calendar
→ **Login BDIP** jika belum login
→ kembali ke QR
→ otomatis mendaftarkan pegawai
→ **Success State**
→ **Pendaftaran Berhasil**
→ **Silahkan menunggu antrian untuk pemeriksaan Rekam Medis.**

Data pegawai diambil dari akun BDIP/HRIS. Pengguna tidak mengisi form peserta pegawai secara manual.

### Non Pegawai

Alur:

`Scan QR`
→ Calendar
→ Form Peserta
→ pengguna mengisi data
→ klik **Daftar Pemeriksaan**
→ form hilang
→ **Success State**

Field:
- NIK
- Nama Lengkap
- Jenis Kelamin
- Instansi / Organisasi
- Email Aktif
- No. Handphone
- Tanda Tangan

Success message:

> **Pendaftaran Berhasil**  
> Pendaftaran Anda berhasil.  
> **Silahkan menunggu antrian untuk pemeriksaan Rekam Medis.**

## 4. QR Agenda / Rapat

Alur awal:

`Scan QR`
→ pilihan:

- **Pegawai Kantor SAR Surabaya**
- **Non Pegawai Kantor SAR Surabaya**

### Pegawai

`Pegawai`
→ Login BDIP
→ kembali ke QR
→ simpan kehadiran
→ **Success State**

### Non Pegawai

Field minimal:
- Nama Lengkap
- Instansi / Organisasi
- Email
- No. Handphone
- Tanda Tangan

Setelah **Simpan Kehadiran**:
- form hilang
- tampil Success State
- tidak menampilkan form disabled

## 5. Aturan UX

### Jangan dilakukan

- Membiarkan form tetap terlihat setelah berhasil.
- Hanya men-disable input lalu menampilkan pesan sukses di bawah form.
- Meminta pengguna mengisi ulang data setelah berhasil.
- Mengarahkan pengguna kembali ke form setelah pendaftaran sukses.
- Membuat desain success state berbeda-beda untuk setiap modul tanpa alasan.

### Harus dilakukan

- Ganti seluruh isi area form dengan Success State.
- Gunakan gaya visual yang sama.
- Gunakan judul **Pendaftaran Berhasil** sebagai standar.
- Gunakan pesan tindak lanjut yang jelas.
- Mobile-first dan nyaman digunakan setelah scan QR melalui kamera HP.

## 6. Pola Implementasi

Success state dapat dilakukan dengan:

1. Server-side render setelah proses berhasil; atau
2. Client-side mengganti seluruh isi card/form setelah API mengembalikan `status=success`.

Yang penting hasil akhirnya sama:

`FORM` → **SUBMIT** → `SUCCESS STATE`

Bukan:

`FORM` → **SUBMIT** → `FORM DISABLED + PESAN`

## 7. Catatan Pengembangan

Dokumen ini adalah acuan sebelum membuat atau mengubah halaman QR baru.

Jika ada kebutuhan khusus suatu modul, kebutuhan khusus tersebut boleh menambah informasi pada Success State, tetapi tidak boleh menghilangkan prinsip utama:
**setelah berhasil, form harus hilang dan pengguna harus mendapatkan konfirmasi yang jelas.**
