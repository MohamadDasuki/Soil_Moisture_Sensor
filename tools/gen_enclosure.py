"""Parametric 3D-printable enclosure for the Moisture Sensor (Rev C PCB).

Run with FreeCAD's command-line interpreter:
    "C:\\Users\\<you>\\AppData\\Local\\Programs\\FreeCAD 1.1\\bin\\freecadcmd.exe" tools\\gen_enclosure.py

Outputs (enclosure/):
    body.step/.stl   - tub: OLED window, OLED pocket, PCB clips, battery bay, button hole
    lid.step/.stl    - snap-on back lid with OLED hold-down posts and battery door rails
    door.step/.stl   - sliding dovetail battery door with flex detent
    assembly.step    - everything + PCB + dummy OLED / cells / button for fit checks
    STLs are already in print orientation (no supports needed).

Coordinate convention (assembled): x = width, y = length measured DOWN from the
top end (button end), z = height above the front (display) face, which is the
print bed for the body.  FreeCAD Y = -y.
"""
import os, sys, math
import FreeCAD as App
import Part, Mesh, MeshPart
from FreeCAD import Vector as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "enclosure")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- parameters
WALL, FRONT, LID_T = 2.0, 1.6, 1.8          # wall / front face / lid thickness
IW = 38.0                                    # inner width
ID = 15.0                                    # inner depth (floor -> wall top)
ZF = FRONT                                   # floor (inner front face) z
ZT = FRONT + ID                              # wall top / lid inner face z
R_OUT = 3.0

# PCB (24 x 19, components facing the lid, rotated 180 deg)
PCB_W, PCB_H, PCB_T = 24.0, 19.0, 1.6
PCB_X0, PCB_Y0 = 12.0, 3.0                   # global top-left corner
RAIL = 3.0                                   # PCB underside height above floor
Z_PCB = ZF + RAIL                            # PCB bottom face
Z_HOOK = Z_PCB + PCB_T + 0.1                 # underside of clip lips
CLIP_T, CLIP_GAP, CLIP_LIP = 0.8, 0.15, 0.5

# OLED module (ELEGOO 0.96" SSD1306) - VERIFY WITH CALIPERS
OLED_W, OLED_H = 27.3, 27.8                  # module PCB
OLED_PCB_T = 1.2
GLASS_W, GLASS_H, GLASS_T = 26.7, 19.3, 1.6
GLASS_TOP = 4.6                              # header edge -> glass top
VIEW_W, VIEW_H, VIEW_TOP = 23.74, 12.86, 1.6 # viewing area, offset below glass top
MX0, MY0 = IW / 2 - OLED_W / 2, 25.5         # module top-left (header edge on top)
Z_OLED_BACK = ZF + GLASS_T + OLED_PCB_T

# Button (Twidec PBS-110, 7 mm, M7 thread, ~11 mm hex nut)
BTN_X, BTN_Z, BTN_HOLE = 6.8, ZF + 7.5, 7.3

# Batteries 3 x AAA side by side, series wired with generic AAA contacts
CELL_D, CELL_L = 10.5, 44.5
CELL_X = [8.0, 19.0, 30.0]
CELL_ZC = ZF + 1.0 + CELL_D / 2
FENCE_T, SLOT_T = 2.4, 0.8
BAY_Y0 = MY0 + OLED_H + 0.3                  # top fence starts here (also OLED stop)
CELL_SPACE = 48.5                            # between fence faces (cell + spring)
FENCE_TOP = ZF + 11.6
IL = BAY_Y0 + 2 * FENCE_T + CELL_SPACE       # inner length

# Sensor cable entry (U-notch at the split line, left wall in this frame)
CABLE_Y, CABLE_W, CABLE_H = 23.1, 3.5, 3.2

DOOR_Y0 = BAY_Y0 - 0.6
DOOR_IN = 4.0                                # door outer-face inset from inner wall

# ---------------------------------------------------------------- helpers
def B(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, -y1, z0))

def rbox(x0, x1, y0, y1, z0, z1, r):
    b = B(x0, x1, y0, y1, z0, z1)
    ed = [e for e in b.Edges if abs(e.Vertexes[0].Z - e.Vertexes[1].Z) > 1e-6]
    return b.makeFillet(r, ed)

def prism(profile, side, e, w0, w1):
    """profile: [(n, z)] with n measured outward from edge e. side: x+, x-, y+, y-."""
    pts = []
    for n, z in profile:
        if side == "x+": pts.append(V(e + n, -w0, z))
        if side == "x-": pts.append(V(e - n, -w0, z))
        if side == "y+": pts.append(V(w0, -(e + n), z))
        if side == "y-": pts.append(V(w0, -(e - n), z))
    vec = V(0, -(w1 - w0), 0) if side[0] == "x" else V(w1 - w0, 0, 0)
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(vec)

def fuse(shapes):
    s = shapes[0]
    for t in shapes[1:]:
        s = s.fuse(t)
    return s.removeSplitter()

def clip(side, e, w0, w1):
    g, t, zh = CLIP_GAP, CLIP_T, Z_HOOK
    prof = [(g, ZF - 0.01), (g + t, ZF - 0.01), (g + t, zh + 1.4), (g, zh + 1.4),
            (-CLIP_LIP, zh + 0.4), (-CLIP_LIP, zh), (g, zh)]
    sup = [(-1.4, ZF - 0.01), (-0.25, ZF - 0.01), (-0.25, Z_PCB), (-1.4, Z_PCB)]
    return [prism(prof, side, e, w0, w1), prism(sup, side, e, w0, w1)]

def teardrop_y(x, z, d, y0, y1):
    r = d / 2
    c = Part.Face(Part.Wire(Part.makeCircle(r, V(x, -y0, z), V(0, 1, 0))))
    k = r / math.sqrt(2)
    tri = Part.Face(Part.makePolygon([V(x - k, -y0, z + k), V(x + k, -y0, z + k),
                                      V(x, -y0, z + r * math.sqrt(2)), V(x - k, -y0, z + k)]))
    f = c.fuse(tri).removeSplitter()
    f = Part.Face(f.Faces[0].OuterWire) if len(f.Faces) == 1 else f
    return f.extrude(V(0, -(y1 - y0), 0))

def frustum_hole(xc, yc, w, h, z0, z1, grow):
    """Rect hole w x h at z1, growing by `grow` per side at z0 (bed side chamfer)."""
    def rect(ww, hh, z):
        return Part.makePolygon([V(xc - ww / 2, -(yc - hh / 2), z), V(xc + ww / 2, -(yc - hh / 2), z),
                                 V(xc + ww / 2, -(yc + hh / 2), z), V(xc - ww / 2, -(yc + hh / 2), z),
                                 V(xc - ww / 2, -(yc - hh / 2), z)])
    return Part.makeLoft([rect(w + 2 * grow, h + 2 * grow, z0), rect(w, h, z1)], True)

# ---------------------------------------------------------------- body
def make_body():
    body = rbox(-WALL, IW + WALL, -WALL, IL + WALL, 0, ZT, R_OUT)
    body = body.cut(rbox(0, IW, 0, IL, ZF, ZT + 1, 1.0))
    add, cut = [], []

    # OLED window (45 deg chamfer on the outside face; bed side, prints fine)
    vy = MY0 + GLASS_TOP + VIEW_TOP + VIEW_H / 2
    cut.append(frustum_hole(IW / 2, vy, VIEW_W + 0.4, VIEW_H + 0.4, -0.01, 0.8, 0.81))
    cut.append(B(IW / 2 - VIEW_W / 2 - 0.2, IW / 2 + VIEW_W / 2 + 0.2,
                 vy - VIEW_H / 2 - 0.2, vy + VIEW_H / 2 + 0.2, 0.5, ZF + 0.1))

    # OLED pocket: side walls, top-right stop, battery fence is the bottom stop
    c, t, zw = 0.3, 1.2, Z_OLED_BACK + 1.2
    add.append(B(MX0 - c - t, MX0 - c, MY0 + 0.5, BAY_Y0, ZF - 0.01, zw))
    add.append(B(MX0 + OLED_W + c, MX0 + OLED_W + c + t, MY0 - c - t, BAY_Y0, ZF - 0.01, zw))
    add.append(B(MX0 + OLED_W - 6, MX0 + OLED_W + c + t, MY0 - c - t, MY0 - c, ZF - 0.01, zw))
    # corner ledges carry the module PCB outside the glass
    for x0 in (MX0, MX0 + OLED_W - 2.5):
        for y0 in (MY0, MY0 + OLED_H - 2.5):
            add.append(B(x0, x0 + 2.5, y0, y0 + 2.5, ZF - 0.01, ZF + GLASS_T))

    # PCB clips (see README for insertion order)
    gx = lambda lx: PCB_X0 + PCB_W - lx      # PCB local -> global (180 deg)
    gy = lambda ly: PCB_Y0 + PCB_H - ly
    add += clip("x+", PCB_X0 + PCB_W, gy(5.6), gy(3.6))          # local left edge
    add += clip("x-", PCB_X0, gy(6.0), gy(3.0))                   # local right edge
    add += clip("y-", PCB_Y0, gx(15.5), gx(11.5))                 # local bottom edge
    # rigid hook on the local top edge (top-right corner, free of parts)
    e = PCB_Y0 + PCB_H
    add.append(prism([(0.15, ZF - 0.01), (1.35, ZF - 0.01), (1.35, Z_HOOK + 0.9), (-0.6, Z_HOOK + 0.9),
                      (-0.6, Z_HOOK), (0.15, Z_HOOK)], "y+", e, gx(23.3), gx(20.3)))
    add.append(prism([(-1.4, ZF - 0.01), (-0.25, ZF - 0.01), (-0.25, Z_PCB), (-1.4, Z_PCB)],
                     "y+", e, gx(23.3), gx(20.3)))

    # Button hole (teardrop, prints without support)
    cut.append(teardrop_y(BTN_X, BTN_Z, BTN_HOLE, -WALL - 0.1, 0.1))

    # Sensor cable notch + strain-relief posts
    cut.append(B(-WALL - 0.1, 0.1, CABLE_Y - CABLE_W / 2, CABLE_Y + CABLE_W / 2, ZT - CABLE_H, ZT + 0.1))
    for (x, y) in ((2.8, CABLE_Y - 1.1), (5.3, CABLE_Y + 1.1), (7.8, CABLE_Y - 1.1)):
        add.append(Part.makeCylinder(0.9, ZT - 3.0 - ZF + 0.01, V(x, -y, ZF - 0.01)))

    # Battery fences with contact slots and windows
    for (y0, single, double, inner_face) in (
            (BAY_Y0, [CELL_X[0]], (CELL_X[1], CELL_X[2]), BAY_Y0 + FENCE_T),
            (IL - FENCE_T, [CELL_X[2]], (CELL_X[0], CELL_X[1]), IL - FENCE_T)):
        add.append(B(0, IW, y0, y0 + FENCE_T, ZF - 0.01, FENCE_TOP))
        s0 = y0 + (FENCE_T - SLOT_T) / 2
        for xc in single:
            cut.append(B(xc - 5.0, xc + 5.0, s0, s0 + SLOT_T, ZF + 0.6, ZT))
        xm = (double[0] + double[1]) / 2
        cut.append(B(xm - 10.5, xm + 10.5, s0, s0 + SLOT_T, ZF + 0.6, ZT))
        if y0 == BAY_Y0:
            wy0, wy1 = s0 + SLOT_T - 0.01, y0 + FENCE_T + 0.1
        else:
            wy0, wy1 = y0 - 0.1, s0 + 0.01
        for xc in CELL_X:
            cut.append(B(xc - 3.5, xc + 3.5, wy0, wy1, ZF + 1.6, ZT))
    # cell cradles
    for yc in (BAY_Y0 + FENCE_T + 10, IL - FENCE_T - 10):
        s = B(0, IW, yc - 2, yc + 2, ZF - 0.01, ZF + 4.4)
        for xc in CELL_X:
            s = s.cut(Part.makeCylinder(CELL_D / 2 + 0.15, 5, V(xc, -(yc - 2.5), CELL_ZC), V(0, -1, 0)))
        add.append(s)

    # lid snap grooves (left/right walls)
    for ys in LID_TABS:
        cut.append(B(-0.6, 0.01, ys - 3.3, ys + 3.3, ZT - 5.7, ZT - 3.7))
        cut.append(B(IW - 0.01, IW + 0.6, ys - 3.3, ys + 3.3, ZT - 5.7, ZT - 3.7))

    # door detent groove (with lead-in ramp) + fingernail notch on bottom wall
    x0, x1 = IW / 2 - 6.5, IW / 2 + 6.5
    cut.append(prism([(0.3, ZT + 0.1), (0.3, ZT - 0.7), (1.3, ZT - 0.7), (2.1, ZT + 0.1)],
                     "y+", IL, x0, x1))
    cut.append(B(x0 + 0.5, x1 - 0.5, IL + WALL - 0.5, IL + WALL + 0.1, ZT - 1.2, ZT + 0.1))

    return body.fuse(add).cut(fuse(cut)).removeSplitter()

LID_TABS = (MY0 + 12.0, IL - FENCE_T - 22.0)

# ---------------------------------------------------------------- lid
def make_lid():
    z0, z1 = ZT, ZT + LID_T
    lid = rbox(-WALL, IW + WALL, -WALL, IL + WALL, z0, z1, R_OUT)
    # door opening (dovetail: narrow at outer face)
    lid = lid.cut(dovetail(DOOR_IN, DOOR_Y0, IL + WALL + 1, 0.0))
    # alignment lip inside the walls
    lip = rbox(0.2, IW - 0.2, 0.2, IL - 0.2, ZT - 2.0, z0 + 0.01, 0.8).cut(
        B(1.4, IW - 1.4, 1.4, IL - 1.4, ZT - 2.1, z0 + 0.1))
    gaps = [B(-1, 15, -1, 2, ZT - 3, z0),                                   # button nut
            B(-1, 2, CABLE_Y - CABLE_W / 2 - 0.5, CABLE_Y + CABLE_W / 2 + 0.5, ZT - 3, z0),
            B(-1, IW + 1, IL - 2, IL + 1, ZT - 3, z0)]                       # door end
    for ys in LID_TABS:
        gaps += [B(-1, 2, ys - 3.6, ys + 3.6, ZT - 3, z0), B(IW - 2, IW + 1, ys - 3.6, ys + 3.6, ZT - 3, z0)]
    lip = lip.cut(fuse(gaps))
    add = [lip]
    # snap tabs
    prof = [(-1.2, z0 + 0.01), (-1.2, ZT - 5.8), (-0.2, ZT - 5.8), (-0.2, ZT - 5.6),
            (0.45, ZT - 5.0), (0.45, ZT - 4.6), (-0.2, ZT - 3.8), (-0.2, z0 + 0.01)]
    for ys in LID_TABS:
        add.append(prism(prof, "x-", 0.0, ys - 3.0, ys + 3.0))
        add.append(prism(prof, "x+", IW, ys - 3.0, ys + 3.0))
    # OLED hold-down posts on the module corners
    for x0 in (MX0, MX0 + OLED_W - 2.5):
        for y0 in (MY0, MY0 + OLED_H - 2.5):
            add.append(B(x0, x0 + 2.5, y0, y0 + 2.5, Z_OLED_BACK, z0 + 0.01))
    return lid.fuse(add).removeSplitter()

def dovetail(inset, y0, y1, clr):
    """45-deg dovetail prism through the lid thickness; wide at the inner face."""
    z0, z1 = ZT - 0.01, ZT + LID_T + 0.01
    xa, xb = inset + clr, IW - inset - clr          # at outer face
    d = (z1 - z0)
    pts = [V(xa - d, -y0, z0), V(xb + d, -y0, z0), V(xb, -y0, z1), V(xa, -y0, z1)]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, -(y1 - y0), 0))

# ---------------------------------------------------------------- door
def make_door():
    door = dovetail(DOOR_IN, DOOR_Y0 + 0.2, IL + WALL, 0.25)
    door = door.common(B(-5, IW + 5, -5, IL + 10, ZT, ZT + LID_T))
    x0, x1 = IW / 2 - 6.5, IW / 2 + 6.5
    # flex tab: two slots from the end
    door = door.cut(B(x0 - 1.0, x0, IL - 9, IL + WALL + 1, ZT - 1, ZT + 3))
    door = door.cut(B(x1, x1 + 1.0, IL - 9, IL + WALL + 1, ZT - 1, ZT + 3))
    # detent bump under the tab
    bump = prism([(0.6, ZT + 0.01), (1.0, ZT - 0.5), (1.4, ZT - 0.5), (1.8, ZT + 0.01)],
                 "y+", IL, x0 + 0.5, x1 - 0.5)
    door = door.fuse(bump)
    # finger grip grooves on the outer face
    for k in range(4):
        yg = IL - 6 + k * 2.0
        door = door.cut(B(x0 - 6, x1 + 6, yg, yg + 0.8, ZT + LID_T - 0.5, ZT + LID_T + 1))
    return door.removeSplitter()

# ---------------------------------------------------------------- fit-check dummies
def pcb_shape():
    import Import
    doc = App.newDocument("pcb")
    Import.insert(os.path.join(ROOT, "Moisture_Sensor.step"), doc.Name)
    roots = [o for o in doc.Objects if not o.InList and hasattr(o, "Shape") and o.Shape.Solids]
    comp = Part.makeCompound([o.Shape.copy() for o in roots])
    App.closeDocument(doc.Name)
    comp.rotate(V(0, 0, 0), V(0, 0, 1), 180)
    comp.translate(V(100 + PCB_X0 + PCB_W, -(100 + PCB_Y0 + PCB_H), Z_PCB))
    return comp

def dummies():
    d = {}
    d["oled"] = fuse([B(MX0, MX0 + OLED_W, MY0, MY0 + OLED_H, ZF + GLASS_T, Z_OLED_BACK),
                      B(IW / 2 - GLASS_W / 2, IW / 2 + GLASS_W / 2, MY0 + GLASS_TOP,
                        MY0 + GLASS_TOP + GLASS_H, ZF, ZF + GLASS_T)])
    yc0 = BAY_Y0 + FENCE_T + (CELL_SPACE - CELL_L) / 2
    d["cells"] = Part.makeCompound([Part.makeCylinder(CELL_D / 2, CELL_L, V(x, -yc0, CELL_ZC), V(0, -1, 0))
                                    for x in CELL_X])
    d["button"] = Part.makeCylinder(3.5, 16, V(BTN_X, 0, BTN_Z), V(0, -1, 0)).fuse(
        Part.makeCylinder(6.35, 2.0, V(BTN_X, 0, BTN_Z), V(0, -1, 0))).fuse(
        Part.makeCylinder(4.5, 6.0, V(BTN_X, WALL, BTN_Z), V(0, 1, 0)))
    return d

# ---------------------------------------------------------------- build
def export(shape, name, flip=False):
    shape.exportStep(os.path.join(OUT, name + ".step"))
    s = shape.copy()
    if flip:
        s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    bb = s.BoundBox
    s.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
    m = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.02, AngularDeflection=0.15)
    m.write(os.path.join(OUT, name + ".stl"))

if __name__ in ("__main__", "gen_enclosure") and not os.environ.get("ENC_NO_MAIN"):
    body, lid, door = make_body(), make_lid(), make_door()
    for n, s in (("body", body), ("lid", lid), ("door", door)):
        print(n, "valid" if s.isValid() else "INVALID", "solids", len(s.Solids),
              "vol %.1f cm3" % (s.Volume / 1000), "bbox", s.BoundBox)
    export(body, "body")
    export(lid, "lid", flip=True)
    export(door, "door", flip=True)

    pcb = pcb_shape()
    dm = dummies()
    parts = {"body": body, "lid": lid, "door": door}
    others = dict(dm, pcb=pcb)
    print("--- interference (mm3) ---")
    bad = 0
    for pn, p in parts.items():
        for on, o in others.items():
            v = sum(p.common(so).Volume for so in o.Solids)
            print(f"{pn:5s} x {on:7s}: {v:8.3f}")
            bad += v > 0.5   # <0.5 mm3 = coplanar-face numerical slivers
    for a, b_ in (("body", "lid"), ("body", "door"), ("lid", "door")):
        v = parts[a].common(parts[b_]).Volume
        print(f"{a} x {b_}: {v:.3f}")
        bad += v > 0.5   # <0.5 mm3 = coplanar-face numerical slivers
    c = parts["lid"].common(parts["door"]); print("lid/door overlap bbox", c.BoundBox) if c.Volume > 0.05 else None
    print("INTERFERENCES:", bad)
    print("outer size: %.1f x %.1f x %.1f mm" % (IW + 2 * WALL, IL + 2 * WALL, ZT + LID_T))

    asm = Part.makeCompound([body, lid, door, pcb] + list(dm.values()))
    asm.exportStep(os.path.join(OUT, "assembly.step"))

    print("done")
