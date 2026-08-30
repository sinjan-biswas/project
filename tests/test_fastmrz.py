from fastmrz import FastMRZ
import cv2
import json

fast_mrz = FastMRZ()

def extract_passport(image_path):
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")
    
    details = fast_mrz.get_details(image, input_type='numpy')
    return details

if __name__ == "__main__":
    # Replace with path to a real passport scan
    result = extract_passport("sample_passport.jpg")
    print(json.dumps(result, indent=2))
