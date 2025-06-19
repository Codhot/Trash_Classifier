# -- STAGE 1: Build Environment (untuk instalasi PyTorch CPU yang spesifik) --
# Menggunakan base image Python yang lebih kecil dan stabil
FROM python:3.10-slim-buster as builder

# Atur direktori kerja di dalam container
WORKDIR /app

# Nonaktifkan cache pip secara default untuk menjaga ukuran image
ENV PIP_NO_CACHE_DIR=1

# Salin hanya file requirements.txt terlebih dahulu
# Ini memanfaatkan Docker cache layer. Jika requirements.txt tidak berubah,
# layer instalasi pip tidak perlu dibangun ulang.
COPY requirements.txt .

# Instal dependensi Python
# Penting: Menggunakan --index-url untuk memastikan PyTorch versi CPU diunduh
RUN pip install -r requirements.txt --index-url https://download.pytorch.org/whl/cpu

# -- STAGE 2: Production Environment (lebih kecil dan lebih aman) --
# Menggunakan base image yang sama untuk konsistensi, tapi tanpa build tools
FROM python:3.10-slim-buster

# Atur direktori kerja di dalam container produksi
WORKDIR /app

# Salin virtual environment yang sudah dibuat dari stage 'builder'
COPY --from=builder /opt/venv /opt/venv

# Aktifkan virtual environment yang sudah diinstal
ENV PATH="/opt/venv/bin:$PATH"

# Salin semua file aplikasi yang diperlukan
# Perhatikan urutan agar layer cache lebih efisien
COPY Procfile .
COPY app.py .
COPY yolov5 ./yolov5
COPY static ./static

# Expose port yang akan digunakan aplikasi (misalnya 5000, tapi Railway akan override dengan $PORT)
# Ini lebih sebagai dokumentasi dan bisa dihapus jika tidak diperlukan.
EXPOSE 5000

# Command untuk menjalankan aplikasi menggunakan Gunicorn
# Railway akan menginjeksikan variabel $PORT secara otomatis
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:$PORT"]
