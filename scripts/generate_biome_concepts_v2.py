"""
Generate biome concept art v2 — corrected prompts.
Biomes: Flooded Prison, Bone Warrens, Castle Nave, Ruined Belfry, The Solarium
Light: lantern-only in biome 1, golden-white sunlight building from biome 2-5.
Model: imagen-4.0-ultra-generate-001
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
        "filename": "biome-01-flooded-prison.png",
        "prompt": (
            "Dark fantasy video game concept art, wide cinematic side-scrolling metroidvania environment. "
            "A flooded underground prison. Stone cells with iron bars, water covering the floor, reflecting light. "
            "The only light source is a single small old oil lantern hanging from the ceiling, casting a warm amber glow "
            "that barely illuminates the immediate surroundings. The rest of the space fades into total darkness. "
            "Dripping water, moss on stone walls, rusted cell doors hanging open. Chains. "
            "No sunlight whatsoever — only the lantern. Dim, visible but oppressive. "
            "Mood: forgotten, abandoned, the deepest point. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-02-bone-warrens.png",
        "prompt": (
            "Dark fantasy video game concept art, wide cinematic side-scrolling metroidvania environment. "
            "An underground cave system used as ancient catacombs and burial warrens. "
            "Natural cave rock walls carved out into tomb niches stacked floor to ceiling, filled with bones and skulls. "
            "Multiple wall-mounted torches casting warm golden-white light — soft and faint, just enough to see by. "
            "Mysterious glowing runes carved into stone. A few old lanterns on the ground. Dusty burial alcoves. "
            "The golden-white light is dim but present in multiple spots throughout the cave. "
            "Stalactites above. Old stone sarcophagi on the ground. Mystical atmosphere. "
            "Mood: ancient burial place, eerie but not hopeless, the first traces of warmth entering the world. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-03-castle-nave.png",
        "prompt": (
            "Dark fantasy video game concept art, wide cinematic side-scrolling metroidvania environment. "
            "The grand nave of a ruined gothic cathedral inside a dark castle. "
            "Looking from the basement entrance up through massive stone cathedral pillars toward enormous "
            "stained glass windows at the far end. Golden-white sunlight streams powerfully through the windows, "
            "casting dramatic shafts of warm light down across the stone floor and pillars. "
            "The light is clearly coming from outside — bright, directional, beautiful. "
            "Dust motes float in the light shafts. The walls are crumbling, vines on stone. "
            "A ruined altar at the center with a sun wheel symbol. "
            "Mood: grand, sacred space now ruined but still magnificent, golden-white light winning here. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-04-ruined-belfry.png",
        "prompt": (
            "Dark fantasy video game concept art, wide cinematic side-scrolling metroidvania environment. "
            "An outdoor ruined cathedral belfry and broken spires, open to the sky. "
            "The tops of two massive gothic stone towers have been catastrophically shattered and broken open. "
            "Bright golden-white sunlight beams down from directly above, flooding the space between the towers. "
            "The light is strong, almost overwhelming after the darkness below. "
            "Ethereal atmosphere — light rays visible, dust and debris floating in golden light. "
            "Sun wheel carvings on the stone towers, one intact, one shattered. "
            "Stone rubble and fallen arches below. Open sky above with light cloud. "
            "Mood: ascent complete, outdoor, ethereal, sun pouring down, beautiful and exposed. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-05-solarium.png",
        "prompt": (
            "Dark fantasy video game concept art, wide cinematic side-scrolling metroidvania environment. "
            "A grand ancient solar temple, clearly designed to worship the sun, now at the very top of the world. "
            "A massive circular oculus opening in the domed ceiling pours intense golden-white sunlight directly down. "
            "The light is at full intensity — the most radiant in the entire game. "
            "Grand stone columns line the space. A large sun wheel altar at the center, "
            "lit directly by the shaft of golden-white light from the oculus above. "
            "The floor glows warm where the light lands. Dust motes and light particles fill the air. "
            "No enemies, no boss — just the temple, the light, the altar. "
            "The edges of the space fade to shadow but the center is brilliantly lit. "
            "Mood: arrival, sacred stillness, the sun fully reclaimed, triumphant and serene. "
            "Painterly dark fantasy concept art, high detail, cinematic wide composition, no text, no UI, no characters."
        ),
    },
]

def generate_image(prompt, filename):
    print(f"Generating: {filename}...")

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
        print(f"  ERROR: {e.code} — {error_body[:300]}")
        return False

if __name__ == "__main__":
    for biome in BIOMES:
        success = generate_image(biome["prompt"], biome["filename"])
        if not success:
            print(f"  FAILED: {biome['filename']}")
    print("\nDone.")
