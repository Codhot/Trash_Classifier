# -- STAGE 1: Build Environment --
# Menggunakan base image Python yang ringan dan stabil untuk build
# PASTIKAN NAMA ALIAS "builder" ADA DI SINI
FROM python:3.10-slim-buster as builder 

# Atur direktori kerja di dalam container builder
WORKDIR /app

# Nonaktifkan cache pip secara default untuk menjaga ukuran imageee
ENV PIP_NO_CACHE_DIR=1

# Buat virtual environment
RUN python -m venv /opt/venv

# Aktifkan virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Salin hanya file requirements.txt terlebih dahulu untuk memanfaatkan Docker cache layer
COPY requirements.txt .

# Instal dependensi Python di dalam virtual environment
# Gunakan --index-url untuk PyTorch, dan --extra-index-url untuk PyPI standar
RUN pip install -r requirements.txt --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple

# -- STAGE 2: Production Environment (Image Akhir yang Lebih Kecil) --
# Menggunakan base image yang sama untuk konsistensi di environment produksi
FROM python:3.10-slim-buster

# Atur direktori kerja di dalam container produksi
WORKDIR /app

# Salin virtual environment yang sudah diinstal dari stage 'builder'
# PASTIKAN INI MERUJUK KE ALIAS "builder" DARI STAGE 1
COPY --from=builder /opt/venv /opt/venv 

# Aktifkan virtual environment di PATH
ENV PATH="/opt/venv/bin:$PATH"

# Salin semua file aplikasi yang diperlukan ke image final
COPY Procfile .
COPY app.py .
COPY gunicorn_config.py . # SALIN FILE KONFIGURASI GUNICORN
COPY yolov5 ./yolov5
COPY static ./static

# (Opsional) Mengindikasikan port yang didengarkan, untuk dokumentasi
EXPOSE 5000

# Perintah default untuk menjalankan aplikasi menggunakan Gunicorn
# Gunakan -c untuk menentukan file konfigurasi Gunicorn
CMD ["gunicorn", "-c", "gunicorn_config.py", "app:app"] 
