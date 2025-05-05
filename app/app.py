from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import cv2
import numpy as np
from PIL import Image
import io

# --- Fix for PyTorch 2.6 unpickling restrictions ---
from torch.serialization import add_safe_globals
from ultralytics.nn.tasks import DetectionModel
from ultralytics.nn.modules.conv import Conv
import torch.nn as nn
import torch.nn.modules.conv as conv_module  # used for Conv2d

# Allowlist required classes for safe unpickling
add_safe_globals([
    DetectionModel,     # YOLOv8 core model class
    nn.Sequential,      # used within the model architecture
    Conv,               # YOLOv8's custom Conv layer
    conv_module.Conv2d  # standard PyTorch Conv2d layer
])

app = FastAPI()

# --- CORS configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Load YOLOv8 model ---
model = YOLO("best.pt")
class_names = ['G2', 'RAD51']

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    image_bytes = await file.read()
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Run detection with a confidence threshold of 15%
    results = model(img, conf=0.15)[0]
    class_ids = results.boxes.cls.tolist()

    # Count cells
    g2_count = class_ids.count(0)
    rad51_count = class_ids.count(1)
    hr_score = (rad51_count / (rad51_count + 2 * g2_count)) * 100 if (rad51_count + 2 * g2_count) else 0

    # Draw bounding boxes on the image
    boxes = results.boxes.xyxy.cpu().numpy()
    for box, cls_id in zip(boxes, class_ids):
        x1, y1, x2, y2 = map(int, box)
        label = class_names[int(cls_id)]
        color = (0, 255, 0) if label == 'G2' else (0, 0, 255)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Convert annotated image to bytes for response
    _, buffer = cv2.imencode('.jpg', img)
    result_image = io.BytesIO(buffer.tobytes())

    return StreamingResponse(
        result_image,
        media_type="image/jpeg",
        headers={
            "G2-Count": str(g2_count),
            "RAD51-Count": str(rad51_count),
            "HR-Score": f"{hr_score:.2f}"
        }
    )
