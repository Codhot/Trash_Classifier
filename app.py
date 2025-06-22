import os
from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename
import torch
from PIL import Image
import base64
from pathlib import Path
import glob
import shutil

# --- Inisialisasi Aplikasi Flask ---
app = Flask(__name__)

# --- Konfigurasi Path ---
# PROJECT_ROOT akan menjadi direktori root dari repositori Space Anda
PROJECT_ROOT = Path(__file__).resolve().parent

# Pastikan folder 'static' dan sub-folder-nya ada
# Hugging Face Spaces akan meng-reset ini setiap Space restart,
# jadi ini hanya untuk operasi sementara selama sesi.
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'static', 'uploads')
RESULT_FOLDER = os.path.join(PROJECT_ROOT, 'static', 'results')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# --- Load Model YOLOv5 ---
# Pastikan folder 'yolov5' ada di root repositori Space Anda
# (hasil kloning dari https://github.com/ultralytics/yolov5.git)
YOLOV5_LOCAL_REPO_PATH = Path(PROJECT_ROOT / 'yolov5').resolve()

# Path ke weights model 'best.pt' Anda relatif terhadap YOLOV5_LOCAL_REPO_PATH
# Asumsi 'best.pt' ada di yolov5/weights/best.pt
MODEL_WEIGHTS_PATH = Path(YOLOV5_LOCAL_REPO_PATH / 'weights' / 'best.pt').resolve()

# Cek apakah file dan folder model ada sebelum mencoba memuatnya
if not YOLOV5_LOCAL_REPO_PATH.exists() or not YOLOV5_LOCAL_REPO_PATH.is_dir():
    raise FileNotFoundError(f"Error: YOLOv5 repository not found at {YOLOV5_LOCAL_REPO_PATH}. "
                            "Please ensure 'ultralytics/yolov5' is cloned into the 'yolov5' folder "
                            "in your Space's root directory.")
if not MODEL_WEIGHTS_PATH.exists():
    raise FileNotFoundError(f"Error: Model file not found at {MODEL_WEIGHTS_PATH}. "
                            "Please ensure 'best.pt' is in the correct location inside 'yolov5/weights/'.")

try:
    print(f"Loading YOLOv5 model from local source '{YOLOV5_LOCAL_REPO_PATH}' with custom weights from '{MODEL_WEIGHTS_PATH}'...")
    # Menggunakan source='local' karena kita sudah mengkloning repo YOLOv5 secara manual ke dalam Space
    model = torch.hub.load(str(YOLOV5_LOCAL_REPO_PATH), 'custom', path=str(MODEL_WEIGHTS_PATH), source='local')
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
    print("Pastikan dependensi YOLOv5 terinstal (lihat requirements.txt) dan model file 'best.pt' benar.")
    raise # Re-raise the exception to stop the app from running without a model

# --- Fungsi Utility ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Route Utama ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Penanganan file yang diunggah
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Hapus folder hasil temp lama sebelum pemrosesan baru
            # Ini memastikan kita selalu mendapatkan hasil terbaru dalam sesi yang sama
            for folder in glob.glob(os.path.join(RESULT_FOLDER, 'temp*')):
                if os.path.exists(folder):
                    shutil.rmtree(folder)
            
            # --- Proses Gambar dengan YOLOv5 ---
            try:
                img = Image.open(filepath)
                
                # Pastikan model sudah berhasil dimuat sebelum digunakan
                # Variabel 'model' seharusnya sudah global setelah berhasil dimuat di atas
                if 'model' not in globals():
                    return render_template('index.html', image_data=None, labels=None, error="Model not loaded. Please check server logs.")

                results = model(img)
                
                # Simpan hasil ke folder 'temp' di dalam RESULT_FOLDER
                results.save(save_dir=os.path.join(RESULT_FOLDER, 'temp'))

                # Cari folder hasil terbaru (temp, temp2, temp3, dll.)
                result_dirs = [d for d in glob.glob(os.path.join(RESULT_FOLDER, 'temp*')) if os.path.isdir(d)]
                
                if not result_dirs:
                    print(f"No result directories found in {RESULT_FOLDER} after saving results.")
                    return render_template('index.html', image_data=None, labels=None, error="Failed to save results. No output directory found.")
                
                # Ambil folder yang paling baru
                latest_result_dir = max(result_dirs, key=os.path.getmtime)
                print(f"YOLOv5 results saved to: {latest_result_dir}")

                # Cari file gambar hasil di dalam folder hasil terbaru
                result_image_files = []
                for ext in ALLOWED_EXTENSIONS:
                    result_image_files.extend(glob.glob(os.path.join(latest_result_dir, f'*.{ext}')))
                
                if not result_image_files:
                    print(f"No result image files found in {latest_result_dir}.")
                    print(f"Contents of '{latest_result_dir}': {os.listdir(latest_result_dir)}")
                    return render_template('index.html', image_data=None, labels=None, error="No processed image found in result directory.")

                # Ambil gambar hasil pertama yang ditemukan
                result_file = result_image_files[0]
                print(f"Displaying result file: {result_file}")

                # Konversi gambar hasil ke base64 untuk ditampilkan di HTML
                with open(result_file, 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode('utf-8')

                # Dapatkan label dan confidence dari hasil deteksi
                if not results.pandas().xyxy[0].empty:
                    labels = results.pandas().xyxy[0][['name', 'confidence']].to_dict('records')
                else:
                    labels = [] # Tidak ada deteksi
                    print("No objects detected in the image.")

                return render_template('index.html', image_data=img_data, labels=labels, error=None)
            
            except Exception as e:
                print(f"Error during image processing or result retrieval: {e}")
                return render_template('index.html', image_data=None, labels=None, error=f"Error processing image: {str(e)}")
    
    # Render halaman awal jika metode GET
    return render_template('index.html', image_data=None, labels=None, error=None)

# --- Jalankan Aplikasi Flask (untuk deployment di Hugging Face Spaces, Gunicorn akan menanganinya) ---
if __name__ == '__main__':
    # Untuk lingkungan lokal, Anda bisa menggunakan ini.
    # Di Hugging Face Spaces, Gunicorn akan menjalankan aplikasi ini.
    # HF Spaces secara otomatis akan mengekspos aplikasi di port 7860.
    port = int(os.environ.get("HF_APP_PORT", 7860))
    app.run(host='0.0.0.0', port=port)
