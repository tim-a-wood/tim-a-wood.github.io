"""
Generate biome concept art using Google Gemini Imagen.
Model: imagen-3.0-generate-002
Output: artifacts/art-bible/concepts/
"""

import os
import sys
import base64
import urllib.request
import urllib.error
import json

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not set")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts", "art-bible", "concepts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BIOMES = [
    {
        "filename": "biome-01-drowned-halls.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "An ancient gothic cathedral vault completely submerged in dark water. "
            "The water is black and still. Massive stone arches rise from the flood, "
            "their tops disappearing into total darkness above. Hanging chains descend into the water. "
            "Deep beneath the water surface, barely visible, a broken stone sun wheel — a religious icon — "
            "emits a faint dying ember-orange glow, its upper section shattered and missing. "
            "The walls show two layers of damage: ancient slow rot and catastrophic violent fracture. "
            "Almost total darkness. Suffocating, the deepest point of the world. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-02-bone-foundry.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "An ancient industrial forge, once used by a knightly order, now completely perverted. "
            "Massive scaffold towers built from iron beams with skulls and rib bones integrated into the framework. "
            "A bone rib arch spans the center. Central furnace kiln burning with orange fire — the only light source. "
            "Smoke rising. Everything dark, industrial, grotesque. Machinery that failed catastrophically. "
            "Industrial horror, perverted purpose. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-03-overgrown-nave.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "A vast gothic cathedral nave, abandoned and reclaimed by wild nature. "
            "Tall stone pillars wrapped in climbing vines and roots. "
            "A tall gothic stained glass window at the far end letting in cold blue-grey light from outside — "
            "the first light in the world. Stone altar with a faded sun circle symbol, half-covered by creeping vines. "
            "Small faint green bioluminescent nodes on the vines. Floor covered in old stone tiles and moss. "
            "Transitional mood — between darkness and healing, beautiful but melancholy. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-04-shattered-spires.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "Two massive gothic stone cathedral towers, their tops catastrophically broken open to the sky. "
            "Jagged shear lines at the broken tops. A ruined stone arch connects them at the base. "
            "The sky between the towers is visible — pale cold grey clouds with faint warm gold on the horizon. "
            "The sun is near but not visible. "
            "On each tower face: a large carved stone sun wheel emblem — eight pointed rays — weathered but visible. "
            "One sun wheel intact, one partially shattered. Fallen stone rubble between the towers. "
            "Mood: exposure, ascent, the sun is close, the price of catastrophe is visible. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-05-solarium.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "The grand solar temple of an ancient knightly order. "
            "A circular oculus at the top pours a column of warm golden sunlight straight down into the center. "
            "Grand stone columns on both sides. On the altar at center: a large sun wheel symbol lit by the golden shaft. "
            "Dust motes float in the golden column. Floor glowing warm where the light lands. "
            "A massive grotesque dark creature silhouette stands at the altar with arms spread wide — "
            "pure black form against the radiant gold light, reaching claws extended. "
            "The darkness fighting hardest where the light is strongest. Edges of the frame remain dark. "
            "The contrast between radiant gold and absolute black is the entire image. "
            "Mood: final confrontation, beauty and dread simultaneously. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI."
        ),
    },
]

def generate_image(prompt, filename):
    print(f"Generating: {filename}...")

    # Try Imagen 3 first
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-ultra-generate-001:predict?key={API_KEY}"

    payload = json.dumps({
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9",
            "safetyFilterLevel": "block_few",
            "personGeneration": "allow_all",
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        img_b64 = data["predictions"][0]["bytesBase64Encoded"]
        img_bytes = base64.b64decode(img_b64)
        out_path = os.path.join(OUTPUT_DIR, filename)
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        print(f"  Saved: {out_path}")
        return True

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  Imagen 3 error: {e.code} — {error_body[:200]}")
        return False

if __name__ == "__main__":
    for biome in BIOMES:
        success = generate_image(biome["prompt"], biome["filename"])
        if not success:
            print(f"  FAILED: {biome['filename']}")
    print("\nDone.")
