"""
Generate biome concept art for the game art bible using OpenAI image generation.
Model: gpt-image-1 (best available)
Output: artifacts/art-bible/concepts/
"""

import os
import sys
import base64
import urllib.request
import urllib.error
import json

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    print("ERROR: OPENAI_API_KEY not set")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts", "art-bible", "concepts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BIOMES = [
    {
        "filename": "biome-01-drowned-halls.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "An ancient gothic cathedral vault completely submerged in dark water. "
            "The water is black and still, reflecting nothing. Massive stone arches rise from the flood, "
            "their tops disappearing into total darkness above. Hanging chains descend into the water. "
            "Deep beneath the water surface, barely visible, a broken stone sun wheel — a religious icon — "
            "emits a faint dying ember-orange glow, its upper section shattered and missing. "
            "The walls show two layers of damage: ancient slow rot and catastrophic violent fracture. "
            "Faint verdigris traces on submerged stonework. Almost total darkness. "
            "Color palette: near-black (#07090B), dark charcoal (#0D1115), deep slate (#1A2127), "
            "ember orange glow only from the submerged sun wheel. "
            "Mood: suffocating, total defeat, the deepest point of the world. "
            "Art style: painterly dark fantasy concept art, high detail, cinematic composition, "
            "no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-02-bone-foundry.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "An ancient industrial forge district, once used by a knightly order to craft armor and weapons, "
            "now completely perverted. Massive bone scaffolding towers fill the space — iron structural beams "
            "with skulls and ribs integrated directly into the framework. "
            "Central furnace kiln still burning with wrong orange fire, smoke rising. "
            "The fire is the only light source. Bone arches span between towers. "
            "Everything is dark, industrial, grotesque. Signs of both slow rot and catastrophic mechanical failure. "
            "Machinery that ran too long and then broke violently. "
            "Color palette: near-black background, dark charcoal steel, rust-orange furnace glow (#A85B32), "
            "blood-rust staining (#7C3D2B), bone-grey structural elements (#2B343B). "
            "Mood: industrial horror, perverted purpose, wrong fire in the dark. "
            "Art style: painterly dark fantasy concept art, high detail, cinematic composition, "
            "no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-03-overgrown-nave.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "A vast gothic cathedral nave, abandoned and reclaimed by wild nature. "
            "Tall stone pillars still standing, wrapped in vines and roots climbing upward. "
            "High pointed arch windows letting in cold grey-blue light — the first hint of light from outside. "
            "At the far end, a stone altar with a faded sun disc symbol, half-covered by creeping vines, "
            "but still standing. Small fading bioluminescent green nodes on the vines — corruption retreating. "
            "Cooler cleaner grey-blue light beginning to replace the green. "
            "The space feels transitional — between darkness and healing. Beautiful but melancholy. "
            "Color palette: dark slate (#1A2127), charcoal stone (#2B343B), cold grey-blue light from windows, "
            "fading green bioluminescence, neutral stone. "
            "Mood: quiet transition, nature reclaiming the sacred, the world beginning to breathe again. "
            "Art style: painterly dark fantasy concept art, high detail, cinematic composition, "
            "no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-04-shattered-spires.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "Two massive gothic stone spires, their tops catastrophically shattered and broken open to the sky. "
            "The break was violent — jagged shear lines, fallen stone blocks between the towers. "
            "First open air in the game. The sky is visible — pale cold grey transitioning to faint warm gold "
            "on the horizon behind the clouds. The sun is near but not visible. "
            "On the face of the left spire, carved deep into the stone: a large sun wheel emblem, "
            "eight-pointed, weathered but intact — the Order of the Sun's symbol. "
            "On the right spire: the same emblem but one quadrant shattered and missing. "
            "A fallen arch fragment spans between the towers in the mid-ground. Wind-caught dust. "
            "Color palette: dark stone (#1A2127, #2B343B), pale grey-blue sky (#4B5A63), "
            "faint warm gold hint (#C4962A at low opacity) behind clouds, atmospheric haze. "
            "Mood: exposure, ascent, the sun is close, the price of the catastrophic break is visible. "
            "Art style: painterly dark fantasy concept art, high detail, cinematic composition, "
            "no text, no UI, no characters."
        ),
    },
    {
        "filename": "biome-05-solarium.png",
        "prompt": (
            "Dark fantasy video game concept art, side-scrolling metroidvania environment. "
            "The grand solar temple of an ancient knightly order dedicated to the sun. "
            "A massive circular oculus at the top of the dome pours a column of warm golden sunlight "
            "directly down into the center of the space. The light is overwhelming and beautiful after total darkness. "
            "Grand stone columns frame the space. A massive sun wheel symbol — eight-pointed, radiating — "
            "carved into the altar at the center, lit by the shaft of light from above. "
            "Dust motes float in the golden column. The floor where the light lands glows warm. "
            "BUT: a massive, grotesque dark creature silhouette stands at the altar, blocking the sun disc, "
            "arms extended wide. Pure black form against the radiant light. Too-wide shoulders, wrong proportions, "
            "reaching claws. The darkness fighting hardest where the light is strongest. "
            "The edges of the frame are still dark — the light hasn't fully won. "
            "Color palette: warm gold (#C4962A) for the light shaft and oculus, "
            "dark stone columns, near-black creature silhouette, dark edges, "
            "the contrast between radiant gold and absolute black is the entire image. "
            "Mood: the final confrontation, beauty and dread simultaneously, the light is winning but at cost. "
            "Art style: painterly dark fantasy concept art, high detail, cinematic composition, "
            "no text, no UI."
        ),
    },
]

def generate_image(prompt, filename, model="gpt-image-1"):
    print(f"Generating: {filename}...")

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": "1536x1024",
        "quality": "high",
        "output_format": "png",
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=payload,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        # If gpt-image-1 not available, fall back to dall-e-3
        if "model" in error_body.lower() and model != "dall-e-3":
            print(f"  gpt-image-1 unavailable, falling back to dall-e-3...")
            return generate_image(prompt, filename, model="dall-e-3")
        print(f"  ERROR: {e.code} {error_body}")
        return False

    item = data["data"][0]

    # gpt-image-1 returns b64_json; dall-e-3 may return url or b64
    if "b64_json" in item:
        img_bytes = base64.b64decode(item["b64_json"])
        out_path = os.path.join(OUTPUT_DIR, filename)
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        print(f"  Saved: {out_path}")
        return True
    elif "url" in item:
        url = item["url"]
        out_path = os.path.join(OUTPUT_DIR, filename)
        urllib.request.urlretrieve(url, out_path)
        print(f"  Saved: {out_path}")
        return True
    else:
        print(f"  ERROR: unexpected response format: {item.keys()}")
        return False

if __name__ == "__main__":
    for biome in BIOMES:
        success = generate_image(biome["prompt"], biome["filename"])
        if not success:
            print(f"  FAILED: {biome['filename']}")
    print("\nDone.")
