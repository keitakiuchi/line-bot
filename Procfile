web: python main.py
web: gunicorn main:app --workers=2 --worker-class=sync --worker-connections=1000 --max-requests=1000 --max-requests-jitter=100 --timeout=25 --keep-alive=2 --preload
