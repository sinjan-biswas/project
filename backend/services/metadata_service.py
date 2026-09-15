from PIL import Image
from PIL.ExifTags import TAGS


EDITORS = ["photoshop", "gimp", "paint", "lightroom", "snapseed", "pixlr", "affinity"]


def analyze_metadata(image_path: str) -> list[dict]:
    flags = []
    try:
        img = Image.open(image_path)
        exif = img._getexif() or {}
    except Exception:
        return [{"type": "EXIF_READ_ERROR", "severity": "low",
                 "detail": "Could not parse EXIF"}]

    tags = {TAGS.get(k, k): v for k, v in exif.items()}

    if not exif:
        flags.append({
            "type": "MISSING_EXIF",
            "severity": "medium",
            "detail": "No EXIF metadata — screenshot or stripped image",
        })
        return flags

    software = str(tags.get("Software", "")).lower()
    for editor in EDITORS:
        if editor in software:
            flags.append({
                "type": "EDITING_SOFTWARE",
                "severity": "high",
                "detail": f"Edited with {tags.get('Software')}",
            })
            break

    dt = tags.get("DateTime")
    dtd = tags.get("DateTimeDigitized")
    if dt and dtd and dt != dtd:
        flags.append({
            "type": "DATE_INCONSISTENCY",
            "severity": "medium",
            "detail": f"Capture ({dt}) vs digitize ({dtd}) dates differ",
        })

    return flags