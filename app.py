from flask import Flask, render_template, request, jsonify, send_from_directory, Response
import cv2
import os
import datetime
import sqlite3
from ultralytics import YOLO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas

app = Flask(__name__)

app.config['UPLOAD_FOLDER']   = 'uploads'
app.config['VIOLATION_FOLDER'] = 'violations'

os.makedirs(app.config['UPLOAD_FOLDER'],    exist_ok=True)
os.makedirs(app.config['VIOLATION_FOLDER'], exist_ok=True)

DB_NAME = "traffic_fines.db"

print("Loading models...")
bike_model = YOLO('yolov8n.pt')
helmet_model = YOLO('runs/detect/helmet_model3/weights/best.pt')
print("✅ System Ready! Bike + Helmet Detection Active")


def get_stats():
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM violations")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM violations WHERE fine_status='Pending'")
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM violations WHERE fine_status='Paid'")
    paid = c.fetchone()[0]
    conn.close()
    return total, pending, paid


def log_violation(timestamp, image_path):
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute("""
        INSERT INTO violations (plate, timestamp, image_path, fine_status)
        VALUES ('UNKNOWN', ?, ?, 'Pending')
    """, (timestamp, image_path))
    conn.commit()
    conn.close()


def detect_bike_and_helmet(frame):
    violations = []
    annotated_frame = frame.copy()
    
    bike_results = bike_model(frame, conf=0.5)
    bikes_found = []
    
    for box in bike_results[0].boxes:
        cls = int(box.cls)
        if cls == 3:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])
            bikes_found.append({'box': (x1, y1, x2, y2), 'area': frame[y1:y2, x1:x2]})
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(annotated_frame, f"BIKE {conf:.2f}", (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    helmet_results = helmet_model(frame, conf=0.4)
    helmets_found = []
    no_helmet_found = []
    
    for box in helmet_results[0].boxes:
        cls = int(box.cls)
        conf = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        
        if cls == 0:
            helmets_found.append({'box': (x1, y1, x2, y2)})
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"HELMET {conf:.2f}", (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        elif cls == 1:
            no_helmet_found.append({'box': (x1, y1, x2, y2)})
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(annotated_frame, f"NO HELMET {conf:.2f}", (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
    for no_helmet in no_helmet_found:
        nx1, ny1, nx2, ny2 = no_helmet['box']
        rider_near_bike = False
        
        for bike in bikes_found:
            bx1, by1, bx2, by2 = bike['box']
            if not (nx2 < bx1 or nx1 > bx2 or ny2 < by1 or ny1 > by2):
                rider_near_bike = True
                break
        
        if rider_near_bike:
            cv2.rectangle(annotated_frame, (nx1, ny1), (nx2, ny2), (0, 0, 255), 3)
            cv2.putText(annotated_frame, "VIOLATION!", (nx1, ny1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
            violations.append({'type': 'No Helmet on Bike', 'box': (nx1, ny1, nx2, ny2)})
    
    return annotated_frame, violations


@app.route('/')
def dashboard():
    total, pending, paid = get_stats()
    return render_template("index.html", total=total, pending=pending, paid=paid)


@app.route('/api/stats')
def api_stats():
    total, pending, paid = get_stats()
    return jsonify({"total": total, "pending": pending, "paid": paid})


@app.route('/violations_data')
def violations_data():
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute("SELECT id, plate, timestamp FROM violations ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "plate": r[1], "timestamp": r[2]} for r in rows])


@app.route('/violations')
def violations_page():
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute("SELECT id, plate, timestamp, fine_status FROM violations ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("violations.html", violations=rows)


@app.route('/mark_paid/<int:vid>')
def mark_paid(vid):
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute("UPDATE violations SET fine_status = 'Paid' WHERE id = ?", (vid,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


@app.route('/generate_pdf/<int:vid>')
def generate_pdf(vid):
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute("SELECT plate, timestamp, fine_status FROM violations WHERE id = ?", (vid,))
    data = c.fetchone()
    conn.close()
    
    if not data:
        return "Not Found"
    
    plate, timestamp, status = data
    filename = f"challan_{vid}.pdf"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    pdf = pdf_canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    
    pdf.setFillColorRGB(0.04, 0.09, 0.16)
    pdf.rect(0, height - 100, width, 100, fill=True, stroke=False)
    
    pdf.setFillColorRGB(0.22, 0.74, 0.98)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(50, height - 50, "TRAFFIC VIOLATION CHALLAN")
    
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, height - 78, "Helmet AI Monitoring System")
    
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height - 140, "Violation Details")
    
    pdf.setStrokeColorRGB(0.22, 0.74, 0.98)
    pdf.setLineWidth(1)
    pdf.line(50, height - 150, width - 50, height - 150)
    
    pdf.setFont("Helvetica", 12)
    pdf.setFillColorRGB(0.2, 0.2, 0.2)
    
    details = [
        ("Violation ID",   str(vid)),
        ("Plate Number",   plate),
        ("Date & Time",    timestamp),
        ("Fine Amount",    "Rs. 500"),
        ("Fine Status",    status),
        ("Violation Type", "Riding without helmet"),
    ]
    
    y = height - 180
    for label, value in details:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, label + ":")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(220, y, value)
        y -= 30
    
    pdf.setFillColorRGB(0.04, 0.09, 0.16)
    pdf.rect(0, 0, width, 60, fill=True, stroke=False)
    
    pdf.setFillColorRGB(0.22, 0.74, 0.98)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 30, "This challan is system-generated by Helmet AI Monitoring System.")
    
    pdf.save()
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@app.route('/detect', methods=['POST'])
def detect():
    file      = request.files['file']
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath  = os.path.join(app.config['UPLOAD_FOLDER'], f"{timestamp}_{file.filename}")
    file.save(filepath)
    
    img = cv2.imread(filepath)
    annotated_img, violations = detect_bike_and_helmet(img)
    violation_count = len(violations)
    
    if violation_count > 0:
        vio_path = os.path.join(app.config['VIOLATION_FOLDER'], f"violation_{timestamp}.jpg")
        cv2.imwrite(vio_path, annotated_img)
        log_violation(timestamp, vio_path)
    
    result_img = f"result_{timestamp}.jpg"
    cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], result_img), annotated_img)
    
    return jsonify({"result_image": result_img, "no_helmet_count": violation_count})


@app.route('/live_feed')
def live_feed():
    cap = cv2.VideoCapture(0)
    
    def generate():
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            annotated_frame, violations = detect_bike_and_helmet(frame)
            _, buffer = cv2.imencode('.jpg', annotated_frame)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        cap.release()
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == "__main__":
    app.run(debug=True)