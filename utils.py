from PIL import Image
import imagehash

def calculate_phash(image_path: str) -> str:
    try:
        img = Image.open(image_path)
        h = imagehash.phash(img)
        return str(h)  # 64-битный hex
    except Exception as e:
        print("pHash error:", e)
        return None
