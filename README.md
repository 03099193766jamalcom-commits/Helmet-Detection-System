# Helmet AI Monitoring System

A Flask web application that detects motorcycle riders without helmets using YOLOv8, logs each violation to a SQLite database, and generates PDF traffic challans (fine tickets).

The system runs two models on every image or camera frame:

1. **Bike detector:** the pretrained COCO `yolov8n.pt`, keeping class `3` (motorcycle).
2. **Helmet detector:** a custom YOLOv8n model trained on two classes, `helmet` and `no_helmet`.

A **violation** is counted when a `no_helmet` box overlaps a detected motorcycle box. Violations are saved as annotated images and recorded in the database with a default fine of **Rs. 500**.

---

## Features

- **Image detection:** upload an image from the dashboard and get an annotated result with a violation count.
- **Live camera feed:** real-time detection from the default webcam, streamed as MJPEG.
- **Violation logging:** annotated violation images go to `violations/` and a record goes to `traffic_fines.db`.
- **Dashboard:** total, pending and paid fines, compliance and collection rates, and recent violations, refreshed every 3 seconds.
- **Violations management:** list every violation, mark fines as paid, and download a PDF challan for each one (built with ReportLab).

---

## Tech Stack

| Layer      | Technology                                  |
|------------|---------------------------------------------|
| Detection  | Ultralytics YOLOv8 (`yolov8n`), PyTorch     |
| Imaging    | OpenCV                                      |
| Backend    | Flask                                       |
| Database   | SQLite                                      |
| Reports    | ReportLab (PDF challans)                    |
| Frontend   | HTML / CSS / vanilla JavaScript (Jinja2)    |

---

## Project Structure

```
Helmet Detection System/
├── app.py                  # Flask app: routes, detection pipeline, PDF generation
├── database.py             # DB schema, seed data, helper queries (run once to init)
├── helmet.yaml             # YOLO training config (helmet / no_helmet)
├── data.yaml               # Roboflow dataset config
├── requirements.txt
├── yolov8n.pt              # Pretrained COCO model (bike detection)
├── traffic_fines.db        # SQLite database
├── templates/
│   ├── index.html          # Main dashboard
│   ├── violations.html     # Violations management page
│   ├── login.html          # Admin login (not wired up yet)
│   ├── dashboard.html      # Unused placeholder
│   └── result.html         # Unused placeholder
├── static/
│   ├── style.css
│   └── main.js             # Dashboard logic (camera, upload, auto-refresh)
├── runs/detect/helmet_model3/
│   └── weights/best.pt     # Trained helmet model used by app.py
├── train/  valid/  test/   # Training / validation / test images + YOLO labels
├── dataset/, helmet_dataset/  # Additional Roboflow dataset exports
├── test-images/, test_images/ # Sample images for manual testing
├── uploads/                # Uploaded images, result images, generated PDFs
├── violations/             # Annotated images of detected violations
└── Motorbike-Helmet-Detection-System.pptx  # Project presentation
```

---

## Installation

**Prerequisites:** Python 3.10, plus a webcam if you want the live feed.

```bash
python -m venv venv
```

```bash
venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

### Initialize the database

`app.py` does not create the tables on its own, so run this once before the first launch:

```bash
python database.py
```

This creates the `vehicles`, `violations` and `admins` tables and adds sample vehicle records and a default admin account.

---

## Running the App

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

| Route                    | Method | Description                                      |
|--------------------------|--------|--------------------------------------------------|
| `/`                      | GET    | Dashboard                                        |
| `/detect`                | POST   | Upload an image (`file` field) and run detection |
| `/live_feed`             | GET    | MJPEG webcam stream with detections              |
| `/violations`            | GET    | Violations management page                       |
| `/violations_data`       | GET    | Latest 10 violations (JSON)                      |
| `/api/stats`             | GET    | Total, pending and paid counts (JSON)            |
| `/mark_paid/<id>`        | GET    | Mark a violation's fine as paid                  |
| `/generate_pdf/<id>`     | GET    | Download the PDF challan for a violation         |
| `/uploads/<filename>`    | GET    | Serve uploaded and result images                 |

---

## Model Training

The helmet model was trained from `yolov8n.pt` using `helmet.yaml`:

```bash
yolo detect train model=yolov8n.pt data=helmet.yaml epochs=30 imgsz=640 batch=8 name=helmet_model
```

> `helmet.yaml` contains an absolute `path:`. Update it to match your machine before you retrain.

### Results (`runs/detect/helmet_model3`, epoch 30)

| Metric       | Value |
|--------------|-------|
| Precision    | 0.837 |
| Recall       | 0.760 |
| mAP@50       | 0.817 |
| mAP@50-95    | 0.397 |

Curves, confusion matrices and sample predictions are in `runs/detect/helmet_model3/`.

### Dataset

The images come from Roboflow Universe under the **CC BY 4.0** license:

- [Motorcycle Helmet](https://universe.roboflow.com/hajibilal/motorcycle-helmet-q0wmd-cywfg/dataset/1): `helmet`, `no helmet`
- [No Helmet](https://universe.roboflow.com/hajibilal/no-helmet-uf1ed-ucrjn/dataset/2): `bike`, `helmet off`, `helmet on`

---

## Database Schema

```sql
vehicles   (plate TEXT PK, owner_name, contact, bike_model, address)
violations (id INTEGER PK, plate, timestamp, image_path,
            fine_amount INTEGER DEFAULT 500, fine_status TEXT DEFAULT 'Pending')
admins     (id INTEGER PK, username UNIQUE, password)
```

---

## Known Limitations and Future Work

These issues were found while reviewing the code:

- **No number-plate recognition:** every violation is stored with the plate `UNKNOWN`. `easyocr` is listed in the requirements and `models/plate_best.pt` and `ocr/` exist as placeholders, but OCR is not implemented.
- **No authentication:** `login.html` and `verify_admin()` exist, but no route uses them. Anyone who can reach the server can mark fines as paid. The default admin password is also stored in plain text.
- **Live feed does not log violations:** only uploaded images are written to the database.
- **Webcam handling:** each request to `/live_feed` opens a new `VideoCapture(0)`, and the camera is not released when the client disconnects.
- **Upload safety:** uploaded filenames are not sanitized. Use `werkzeug.utils.secure_filename`.
- **State-changing GET request:** `/mark_paid/<id>` changes data through a GET request. It should be a POST request.
- **Hard-coded fine:** Rs. 500 is fixed in `app.py` (PDF) and `main.js` instead of being read from the `fine_amount` column.
- **Metric naming:** the "Compliance Rate" on the dashboard is actually the paid/total ratio, not the share of riders wearing helmets.
- **Box colour:** the "NO HELMET" box uses `(255, 0, 0)`, which OpenCV draws as blue because it uses BGR order.
- **Debug mode:** `app.run(debug=True)` should be turned off in production.
- **Housekeeping:** the `runs/detect/` folder holds many old train and predict runs, the root `index.html` is empty, and `dashboard.html` and `result.html` are unused.

---

## License

The dataset is licensed under CC BY 4.0 (Roboflow Universe). YOLOv8 is licensed under AGPL-3.0 by Ultralytics.
