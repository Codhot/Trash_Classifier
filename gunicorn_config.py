import os

# Get port from environment variable, default to 5000 if not set (for local testing)
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}" 

workers = 1 # Sesuaikan jumlah worker sesuai kebutuhan dan resource Railway kamu
timeout = 120 # Timeout untuk request, bisa disesuaikan
