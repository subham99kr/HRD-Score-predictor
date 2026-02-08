import os
import shutil
import base64
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.inference import full_pipeline_predict
import uuid

app = FastAPI(title="Medical AI: HRD Detection API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  ##############
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. SETUP DIRECTORIES ---
# UPLOAD_DIR = "uploads"
import os
import tempfile

UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- 3. UTILITY FUNCTION (Convert CV2 image to Base64 String) ---
def encode_image_to_base64(image_array):
    """Converts a numpy image (RGB) to a base64 string for JSON response."""
    # Convert RGB back to BGR for OpenCV encoding
    image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
    _, buffer = cv2.imencode('.jpg', image_bgr)
    b64_string = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{b64_string}"

@app.get("/")
async def root():
    return {"message": "HRD backend running."}

@app.post("/predict")
async def predict_cancer(file: UploadFile = File(...)):
    # Validating file
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

    # 1) Save uploaded file temporarily
    file_extension = os.path.splitext(file.filename)[1] # get the extension.
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    temp_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 2. Run predict pipeline
        results = full_pipeline_predict(temp_path)
        
        # 3. Encode image to base64 so that frontend could understand it.
        img_b64 = encode_image_to_base64(results["visualized_img"])
        
        # 4. Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # 5. Return complete data
        return {
            "success": True,
            "cancer_count": results["cancer_count"],
            "g2_count": results["g2_count"],
            "hrd_percent": round(results["hr"], 2),
            "image_data": img_b64,  # Frontend can put this in <img src="...">
            "detection_count": len(results["details"])
        }

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

