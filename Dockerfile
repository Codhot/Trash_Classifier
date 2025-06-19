# -- STAGE 1: Build Environment --
# ... (tidak ada perubahan di sini) ...

# -- STAGE 2: Production Environment (Image Akhir yang Lebih Kecil) --
FROM python:3.10-slim-buster

# Atur direktori kerja di dalam container produksi
WORKDIR /app

# Salin virtual environment yang sudah diinstal dari stage 'builder'
COPY --from=builder /opt/venv /opt/venv

# Aktifkan virtual environment di PATH
ENV PATH="/opt/venv/bin:$PATH"

# Salin semua file aplikasi yang diperlukan ke image final
COPY Procfile .
COPY app.py .
COPY yolov5 ./yolov5
COPY static ./static

# (Opsional) Mengindikasikan port yang didengarkan, untuk dokumentasi
EXPOSE 5000

# Perintah default untuk menjalankan aplikasi menggunakan Gunicorn
# GUNAKAN BENTUK SHELL UNTUK $PORT AGAR DIINTERPRETASIKAN DULU OLEH SHELL
# ATAU PASTIKAN GUNICORN MENDAPATKAN NILAI NYA
CMD gunicorn app:app -b "0.0.0.0:${PORT}"
# ATAU
# CMD ["sh", "-c", "gunicorn app:app -b 0.0.0.0:${PORT}"]
