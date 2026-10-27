"""Generate JLCPCB CPL (pick & place) and BOM from the KiCad board.
Run with KiCad's python:  "C:\Program Files\KiCad\10.0\bin\python.exe" tools\gen_cpl.py"""
import csv, os, re, pcbnew
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b = pcbnew.LoadBoard(os.path.join(ROOT, "Moisture_Sensor.kicad_pcb"))
pts = [pt for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts for pt in (d.GetStart(), d.GetEnd())]
x0 = pcbnew.ToMM(min(p.x for p in pts)); y0 = pcbnew.ToMM(max(p.y for p in pts))  # bottom-left corner
# Not machine-placed: wire pads (J2 OLED, J3 sensor, SW1 button) and DNP UPDI pads (J1)
SKIP = {"J1", "J2", "J3", "SW1"}
# KiCad -> JLCPCB rotation offsets (community-verified JLC conventions)
ROT = [(r"^SOT-23", 180), (r"^SOIC-", 270)]
rows = []
for f in b.GetFootprints():
    ref = f.GetReference()
    if ref in SKIP or f.IsDNP():
        continue
    p = f.GetPosition(); fp = f.GetFPID().GetLibItemName().wx_str()
    rot = f.GetOrientationDegrees()
    rot += next((o for pat, o in ROT if re.match(pat, fp)), 0)
    rows.append([ref, f"{pcbnew.ToMM(p.x) - x0:.3f}mm", f"{y0 - pcbnew.ToMM(p.y):.3f}mm",
                 "Top" if f.GetLayer() == pcbnew.F_Cu else "Bottom", f"{rot % 360:.0f}"])
rows.sort(key=lambda r: (re.sub(r"\d", "", r[0]), int(re.sub(r"\D", "", r[0]))))
os.makedirs(os.path.join(ROOT, "fab"), exist_ok=True)
with open(os.path.join(ROOT, "fab", "CPL_JLCPCB.csv"), "w", newline="") as fh:
    c = csv.writer(fh); c.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]); c.writerows(rows)
print(len(rows), "parts")
# JLCPCB BOM: group placed parts by LCSC number
groups = {}
for f in b.GetFootprints():
    ref = f.GetReference()
    if ref in SKIP or f.IsDNP():
        continue
    lcsc = f.GetFieldText("LCSC") if f.HasField("LCSC") else ""
    key = (f.GetValue(), f.GetFPID().GetLibItemName().wx_str(), lcsc)
    groups.setdefault(key, []).append(ref)
nat = lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r)))
with open(os.path.join(ROOT, "fab", "BOM_JLCPCB.csv"), "w", newline="") as fh:
    c = csv.writer(fh); c.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (val, fp, lcsc), refs in sorted(groups.items(), key=lambda kv: nat(sorted(kv[1], key=nat)[0])):
        c.writerow([val, ",".join(sorted(refs, key=nat)), fp, lcsc])
print(len(groups), "BOM lines")