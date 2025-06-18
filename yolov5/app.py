import os
from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename
import torch
from PIL import Image
import base64
from pathlib import Path
import glob
import shutil
import pathlib

# Fix for Windows path issues with pathlib in some environments (if needed)
temp = pathlib.PosixPath
pathlib.PosixPath = pathlib.WindowsPath

app = Flask(__name__)

# --- Konfigurasi Path ---
# PROJECT_ROOT akan menjadi direktori 'trash_classifier'
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'static', 'uploads')
RESULT_FOLDER = os.path.join(PROJECT_ROOT, 'static', 'results')

# Pastikan folder ada
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# --- Load Model YOLOv5 ---
# Path ke repository YOLOv5 yang akan diunduh/cache oleh torch.hub
# Biasanya akan disimpan di C:\Users\YourUser\.cache\torch\hub\ultralytics_yolov5
YOLOV5_REPO_PATH = 'ultralytics/yolov5'

# Path ke weights model 'best.pt' kamu relatif terhadap root project atau direktori yolov5 yang sudah di-cache.
# Kita asumsikan 'best.pt' ada di yolov5/weights/best.pt relative to the trash_classifier folder
# atau di dalam folder yolov5 yang diunduh torch.hub
MODEL_WEIGHTS_PATH = Path(PROJECT_ROOT / 'yolov5' / 'weights' / 'best.pt').resolve()

# Cek apakah file model ada sebelum mencoba memuatnya
if not MODEL_WEIGHTS_PATH.exists():
    raise FileNotFoundError(f"Error: Model file not found at {MODEL_WEIGHTS_PATH}. Please ensure 'best.pt' is in the correct location.")

try:
    print(f"Loading YOLOv5 model from '{YOLOV5_REPO_PATH}' with custom weights from '{MODEL_WEIGHTS_PATH}'...")
    # Mengurangi kemungkinan rate limit:
    # 1. Hapus force_reload=True: Model hanya akan diunduh sekali jika belum ada di cache.
    # 2. Gunakan source='local' jika repository sudah di-cache/diunduh.
    #    Namun, torch.hub.load dengan path custom weights sudah cukup pintar mencari.
    #    Yang paling penting adalah tidak menggunakan force_reload=True secara terus-menerus.
    
    # Untuk pertama kali run, jika repo belum ada di cache, torch.hub akan mengunduhnya.
    # Setelah itu, ia akan menggunakan versi cache.
    model = torch.hub.load(YOLOV5_REPO_PATH, 'custom', path=str(MODEL_WEIGHTS_PATH))
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
    print("Pastikan Anda memiliki koneksi internet untuk unduhan awal repository YOLOv5 oleh torch.hub.")
    print("Atau, jika Anda sudah mengkloning 'ultralytics/yolov5' secara manual, coba arahkan torch.hub.load ke folder lokal tersebut.")
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
            # Ini memastikan kita selalu mendapatkan hasil terbaru
            for folder in glob.glob(os.path.join(RESULT_FOLDER, 'temp*')):
                if os.path.exists(folder):
                    shutil.rmtree(folder)
            
            # --- Proses Gambar dengan YOLOv5 ---
            try:
                img = Image.open(filepath)
                # Pastikan model sudah berhasil dimuat sebelum digunakan
                if 'model' not in locals() and 'model' not in globals():
                    return render_template('index.html', image_data=None, labels=None, error="Model not loaded. Please check server logs.")

                results = model(img)
                
                # Simpan hasil ke folder 'temp' di dalam RESULT_FOLDER
                # YOLOv5 akan membuat sub-folder seperti 'temp', 'temp2', dst.
                # Kita perlu mencari folder terbaru ini.
                results.save(save_dir=os.path.join(RESULT_FOLDER, 'temp'))

                # Cari folder hasil terbaru (temp, temp2, temp3, dll.)
                # Ini adalah pola yang digunakan oleh YOLOv5 saat menyimpan hasil berulang kali.
                # Kita cari folder yang paling baru dimodifikasi.
                result_dirs = [d for d in glob.glob(os.path.join(RESULT_FOLDER, 'temp*')) if os.path.isdir(d)]
                
                if not result_dirs:
                    print(f"No result directories found in {RESULT_FOLDER} after saving results.")
                    return render_template('index.html', image_data=None, labels=None, error="Failed to save results. No output directory found.")
                
                # Ambil folder yang paling baru
                latest_result_dir = max(result_dirs, key=os.path.getmtime)
                print(f"YOLOv5 results saved to: {latest_result_dir}")

                # Cari file gambar hasil di dalam folder hasil terbaru
                # YOLOv5 biasanya menyimpan gambar hasil langsung di dalam folder 'expN'.
                result_image_files = []
                for ext in ALLOWED_EXTENSIONS: # Cek semua ekstensi yang diizinkan
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
                # Pastikan hasil tidak kosong sebelum mengakses pandas
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

# --- Jalankan Aplikasi Flask ---
if __name__ == '__main__':
    # Mode debug=True harus dihindari di produksi
    app.run(debug=True, host='0.0.0.0', port=5000)