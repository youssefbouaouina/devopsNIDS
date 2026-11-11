"""Render the presentation slides (1920x1080 HTML) to images and build a .pptx.

Usage: python deck_to_pptx.py <deck_dir> <output.pptx>
  deck_dir holds project/deck.json and project/slides/<id>.html
Each slide becomes a full-slide picture; its <aside> speaker notes go into the notes page.
"""
import json
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright
from pptx import Presentation
from pptx.util import Emu

deck = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2]).resolve()
repo = pathlib.Path(__file__).resolve().parents[2]
shots = repo / "docs" / "screenshots"

BLOBS = {
    "c8527a12437c77197054cc5ed49e82d3": shots / "01a-jenkins-stages-detail.jpg",
    "03bac4f11b394a353d03eefb3ca81f6f": shots / "01-jenkins-stage-view.jpg",
    "4b7315aa0f128fbfceaa8d7ae6560282": shots / "02-jenkins-artifacts.jpg",
    "0d1bc4459fa8ca4b2e1a2fb0bb659b82": shots / "03-secrets-scan.png",
    "f1143fb4996dbddbede2a6b1f552876e": shots / "06-retire.png",
    "4571022fa1ef8e3c4aeeb0079c897b50": shots / "08-sonarqube.jpg",
    "3c8ef07fc07803ce60edbdc709985fca": shots / "10-gauntlt.png",
    "15d67cef353c8cdeca7dfab22190c772": shots / "11-zap.png",
    "d3c00689f2ab75b3f7edf4342e781d39": shots / "12-prometheus-alerts.jpg",
    "023cf61b9c22acce924e89273509fb3c": shots / "13-grafana.jpg",
    "1c4a883f3c7064561fea4d81cc298f0c": repo / "lab1-evidence" / "cap1.PNG",
    "ff386e28803e45a880915f3757ad9086": shots / "05b-trivy-sca-summary.png",
    "544742ff0f40e676c0c723e4531ec1de": shots / "11b-zap-summary.png",
    "3caea1f2c010efe4a77199de36d04b2f": shots / "02b-jenkins-artifacts-list.png",
}

index = json.loads((deck / "project" / "deck.json").read_text(encoding="utf-8"))
fonts = sorted({f["href"] for f in index["faces"].values() if "href" in f})

PAGE = """<!doctype html><html><head><meta charset="utf-8">{links}<style>
* {{ margin:0; box-sizing:border-box; }}
html, body {{ width:1920px; height:1080px; overflow:hidden; }}
section {{ position:relative; width:1920px; height:1080px; overflow:hidden; }}
h1 {{ font-size:96px; font-weight:600; line-height:1.1 }}
h2 {{ font-size:64px; font-weight:600; line-height:1.15 }}
h3 {{ font-size:44px; font-weight:600; line-height:1.2 }}
p {{ line-height:1.4 }}
table {{ border-collapse:collapse; width:100%; }}
th, td {{ padding:0.35em 0.6em; text-align:left; vertical-align:top; border-bottom:1px solid #C9CEC6; }}
th {{ font-weight:600; border-bottom:2px solid #0F1B2D; }}
</style></head><body>{body}</body></html>"""

frames = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    for sid in index["order"]:
        html = (deck / "project" / "slides" / f"{sid}.html").read_text(encoding="utf-8")
        notes = ""
        m = re.search(r"<aside>(.*?)</aside>", html, re.S)
        if m:
            notes = m.group(1).strip()
            html = html.replace(m.group(0), "")
        for blob, path in BLOBS.items():
            html = html.replace(f"/_blob/{blob}", path.as_uri())
        doc = PAGE.format(links="".join(f'<link rel="stylesheet" href="{h}">' for h in fonts), body=html)
        tmp = out.parent / f"_slide_{sid}.html"
        tmp.write_text(doc, encoding="utf-8")
        page.goto(tmp.as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)
        png = out.parent / f"_slide_{sid}.png"
        page.screenshot(path=str(png))
        tmp.unlink()
        frames.append((sid, png, notes))
        print("rendered", sid, flush=True)
    browser.close()

prs = Presentation()
prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)  # 16:9
blank = prs.slide_layouts[6]
for sid, png, notes in frames:
    slide = prs.slides.add_slide(blank)
    slide.shapes.add_picture(str(png), 0, 0, width=prs.slide_width, height=prs.slide_height)
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    png.unlink()
prs.save(str(out))
print("saved", out)
