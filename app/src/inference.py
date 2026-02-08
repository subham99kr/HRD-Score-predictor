import cv2
from sahi.predict import get_sliced_prediction
from sahi import AutoDetectionModel
import numpy as np
import torch
import joblib
from src.features import extract_features_single
from src.architecture import load_medical_model
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MedicalPipeline")


device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Initializing models on device: {device}")


SCALER_PATH = "models/scaler.pkl"
YOLO_PATH = "models/yolo_best.pt"
HYBRID_PATH = "models/medical_model_silu.pth"

try:
    scaler = joblib.load(SCALER_PATH)
    # model = HybridCNN().to(device)
    # checkpoint = torch.load(HYBRID_PATH, map_location=device)
    # model.load_state_dict(checkpoint["model_state"])
    # model.eval()
    model = load_medical_model(HYBRID_PATH, device)

    detection_model = AutoDetectionModel.from_pretrained(
        model_type="yolov8",
        model_path=YOLO_PATH,
        confidence_threshold=0.05,
        device=device
    )
    logger.info("🟩 All models loaded successfully.")
except Exception as e:
    logger.error(f"❌ Failed to load models: {str(e)}")
    raise

def full_pipeline_predict(image_path):
    logger.info(f"🚀 Starting processing for image: {image_path}")

    # Load original for drawing, and gray for processing
    image_color = cv2.imread(image_path)
    if image_color is None:
        logger.error(f"🔴 File not found or invalid: {image_path}")
        return {"error": "Image not found"}
    
    image_color = cv2.cvtColor(image_color, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(image_color, cv2.COLOR_RGB2GRAY)

    logger.info("🔰 Running SAHI sliced inference...")
    result = get_sliced_prediction(
        image_path,
        detection_model,
        slice_height=256,
        slice_width=256,
        overlap_height_ratio=0.2,
        overlap_width_ratio=0.2
    )
    cancer_count = 0
    g2_count = 0
    outputs = []
    
    # Define colors (RGB)
    CANCER_COLOR = (255, 0, 0) # Red
    G2_COLOR = (0, 255, 0)     # Green

    logger.info(f"👀 Found {len(result.object_prediction_list)} initial YOLO detections.")

    for obj in result.object_prediction_list:
        cls = obj.category.id
        conf = obj.score.value

        # box = obj.bbox.to_xyxy()
        # x1, y1, x2, y2 = map(int, box)
        box = obj.bbox
        x1, y1, x2, y2 = map(int, [box.minx, box.miny, box.maxx, box.maxy])

        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        # filtering few cells
        h, w = crop.shape
        if(h <= 12 or w <= 12): continue;
        if(h >= 40 or w >= 40): continue;
        target_size = 64
        
        if h > target_size or w > target_size:
            crop64 = cv2.resize(crop, (target_size, target_size))
            mask = np.ones((target_size, target_size), dtype=np.uint8)
        else:
            crop64 = np.zeros((target_size, target_size), dtype=np.uint8)
            mask = np.zeros((target_size, target_size), dtype=np.uint8)
            
            y_off = (target_size - h) // 2
            x_off = (target_size - w) // 2
            
            crop64[y_off:y_off+h, x_off:x_off+w] = crop
            mask[y_off:y_off+h, x_off:x_off+w] = 1 

        feat = extract_features_single(crop64, mask)
        feat = scaler.transform([feat])

        img_tensor = torch.tensor(crop64).unsqueeze(0).unsqueeze(0).float()/255
        feat_tensor = torch.tensor(feat).float().to(device)
        img_tensor = img_tensor.to(device)

        with torch.no_grad():
            logits = model(img_tensor, feat_tensor)
            probs = torch.softmax(logits, 1)[0].cpu().numpy()

        cancer_prob, g2_prob = probs

        # If YOLO confidence is good then go with it.
        if conf > 0.75:
            if cls == 0:  # Assuming 0 is Cancer in your YOLO model
                label = ""
                color = G2_COLOR
                g2_count += 1
                
            else:
                label = ""
                color = CANCER_COLOR
                cancer_count += 1
                
                
        # Defer to Hybrid CNN probabilities
        else:
            Y_c=conf
            Y_g=1-conf
            if(cls==1):
                Y_c = 1-conf
                Y_g = conf
            if(g2_prob-cancer_prob > (0.2) ):
                label = ""
                color = CANCER_COLOR
                cancer_count += 1
            else:
                label = ""
                color = G2_COLOR
                g2_count += 1

        # Draw Rectangle and Label on the color image
        cv2.rectangle(image_color, (x1, y1), (x2, y2), color, 1)
        # label_text = f"{label} {cancer_prob:.2f}"
        # cv2.putText(image_color, label_text, (x1, max(15, y1-10)), 
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        outputs.append({
            "box": box,
            "yolo_class": cls,
            "yolo_conf": conf,
            "cnn_cancer_prob": float(cancer_prob),
            "cnn_g2_prob": float(g2_prob)
        })

    # # Display the final visualized image
    # plt.figure(figsize=(14, 14))
    # plt.imshow(image_color)
    # plt.title(f"Predictions: Cancer={cancer_count}, G2={g2_count}")
    # plt.axis("off")
    # plt.show()

    # print("\nDetected Cancer:", cancer_count)
    # print("Detected G2:", g2_count)
    hr_ratio = (((cancer_count)*1.00)/((cancer_count+g2_count)*1.00))*100
    logger.info(f"✅ Processing complete. Cancer: {cancer_count}, G2: {g2_count}, HR: {hr_ratio:.2f}%")

    return {
        "cancer_count": cancer_count,
        "g2_count": g2_count,
        "hr": hr_ratio,
        "details": outputs,
        "visualized_img": image_color
    }