"""Generate, autoroute and pour the Moisture_Sensor PCB.

Run with KiCad's bundled python:  python gen_pcb.py [--route]
"""
import os, sys, subprocess, glob
import pcbnew
from pcbnew import VECTOR2I, FromMM as MM
from sexp import parse, find

PRJ = r"C:\Users\dasukim\Desktop\Kicad\Moisture Sensor"
NAME = "Moisture_Sensor"
FPLIB = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
KCLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
HERE = os.path.dirname(os.path.abspath(__file__))

W, H = 24.0, 19.0          # board size (mm)
OX, OY = 100.0, 100.0      # board origin on the page
R_CORNER = 1.0
P254 = 2.54
YB = H - 1.8               # bottom-edge pad row
MIN_TRACK = 0.2            # board minimum track width (mm)
EDGE_CLR = 0.5             # copper-to-board-edge clearance (mm)

# ref: (x, y, rot_deg, side)   coordinates relative to board top-left
# 2.54 mm TH pad rows at rot 90 run left->right from pin 1
PLACE = {
    "J2": (1.8, 1.6, 90, "F"),        # OLED pads: GND VCC SCL SDA (top edge)
    "J3": (13.0, 1.6, 90, "F"),       # soil sensor pads: GND VCC AOUT (top edge)
    "J1": (2.0, YB, 90, "F"),         # UPDI pads: UPDI GND VBAT (bottom edge)
    "SW1": (W - 2.0 - P254, YB, 90, "F"),  # panel button leads (bottom edge)
    "J5": (2.6, 7.2, 0, "F"),         # battery lead pads (+ top, - below)
    "Q1": (2.5, 13.4, 0, "F"),
    "C1": (6.0, 13.4, 90, "F"),
    "C2": (8.4, 6.0, 90, "F"),
    "U1": (13.5, 9.6, 0, "F"),
    "U2": (20.5, 6.0, 0, "F"),
    "C6": (18.6, 9.4, 90, "F"),
    "C4": (20.6, 9.4, 90, "F"),
    "C5": (22.6, 9.4, 90, "F"),
    "C3": (18.4, 13.0, 90, "F"),
    "R3": (19.95, 13.0, 90, "F"),
    "R1": (21.45, 13.0, 90, "F"),
    "R2": (22.95, 13.0, 90, "F"),
}

SILK = [  # (text, x, y, rot, side)
    ("G", 1.8, 3.9, 0, "F"), ("V", 4.34, 3.9, 0, "F"), ("C", 6.88, 3.9, 0, "F"), ("D", 9.42, 3.9, 0, "F"),
    ("G", 13.0, 3.9, 0, "F"), ("V", 15.54, 3.9, 0, "F"), ("A", 18.08, 3.9, 0, "F"),
    ("OLED", 5.6, 3.9, 0, "B"),
    ("SENSOR", 15.54, 3.9, 0, "B"),
    ("U", 2.0, YB - 2.3, 0, "B"), ("G", 4.54, YB - 2.3, 0, "B"), ("V", 7.08, YB - 2.3, 0, "B"),
    ("UPDI", 4.54, YB - 3.6, 0, "B"),
    ("BTN", W - 2.0 - P254 / 2, YB - 2.3, 0, "B"),
    ("B+", 4.7, 7.2, 0, "B"), ("B-", 4.7, 9.74, 0, "B"),
    ("SOIL METER rC", 13.5, 15.0, 0, "B"),
]
# user-added back-silk credit (from KiCad edit 2836a30)
CREDIT = ("MOHAMAD DASUKI\nRev 1.0.0", 15.5, 11.5)


def netlist():
    net_file = os.path.join(HERE, NAME + ".net")
    subprocess.run([KCLI, "sch", "export", "netlist", "-o", net_file,
                    os.path.join(PRJ, NAME + ".kicad_sch")], check=True, capture_output=True)
    root = parse(open(net_file, encoding="utf-8").read())
    comps = {}
    for c in find(find(root, "components")[0], "comp"):
        g = lambda k: find(c, k)[0][1] if find(c, k) else ""
        comps[g("ref")] = dict(value=g("value"), footprint=g("footprint"), uuid=find(c, "tstamps")[0][1],
                               dnp=any(find(p, "name")[0][1] == "dnp" for p in find(c, "property")),
                               fields={f[1][1]: (f[2] if len(f) > 2 else "")
                                       for fl in find(c, "fields") for f in find(fl, "field")})
    nets = {}
    for n in find(find(root, "nets")[0], "net"):
        name = find(n, "name")[0][1]
        for node in find(n, "node"):
            nets[(find(node, "ref")[0][1], find(node, "pin")[0][1])] = name
    os.remove(net_file)
    return comps, nets


def P(x, y):
    return VECTOR2I(MM(OX + x), MM(OY + y))


def add_line(b, a, c, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(a); s.SetEnd(c); s.SetLayer(layer); s.SetWidth(MM(w))
    b.Add(s)


def add_arc(b, center, start, angle):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(center); s.SetStart(start); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T), True)
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
    b.Add(s)


def outline(b, d=0.0):
    """Rounded-rect Edge.Cuts; d > 0 insets it (used only for the router so it keeps EDGE_CLR from the real edge)."""
    r = R_CORNER - d
    add_line(b, P(d + r, d), P(W - d - r, d)); add_line(b, P(W - d, d + r), P(W - d, H - d - r))
    add_line(b, P(W - d - r, H - d), P(d + r, H - d)); add_line(b, P(d, H - d - r), P(d, d + r))
    add_arc(b, P(W - d - r, d + r), P(W - d - r, d), 90)
    add_arc(b, P(W - d - r, H - d - r), P(W - d, H - d - r), 90)
    add_arc(b, P(d + r, H - d - r), P(d + r, H - d), 90)
    add_arc(b, P(d + r, d + r), P(d, d + r), 90)


def edge_items(b):
    return [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]


def zone(b, net, layer, prio):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer); z.SetNet(net); z.SetAssignedPriority(prio)
    z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2))
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)   # solid connection (also for the hand-soldered wire pads)
    ol = z.Outline(); ol.NewOutline()
    i, c = EDGE_CLR, 1.5   # inset from edge, chamfer to clear the rounded corners
    for x, y in [(c, i), (W - c, i), (W - i, c), (W - i, H - c), (W - c, H - i), (c, H - i), (i, H - c), (i, c)]:
        ol.Append(MM(OX + x), MM(OY + y))
    b.Add(z)


def build():
    comps, nets = netlist()
    b = pcbnew.NewBoard(os.path.join(PRJ, NAME + ".kicad_pcb"))
    ds = b.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetTrackWidth(MM(0.25)); nc.SetClearance(MM(0.2))
    nc.SetViaDiameter(MM(0.6)); nc.SetViaDrill(MM(0.3))
    ds.m_TrackMinWidth = MM(MIN_TRACK); ds.m_MinClearance = MM(0.15)
    ds.m_ViasMinSize = MM(0.5); ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(EDGE_CLR)
    ds.m_HoleToHoleMin = MM(0.25)

    netobj = {}
    for name in sorted(set(nets.values())):
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
        netobj[name] = ni

    for ref, c in comps.items():
        lib, fpn = c["footprint"].split(":")
        fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), fpn)
        fp.SetReference(ref); fp.SetValue(c["value"])
        fp.SetFPIDAsString(c["footprint"])
        fp.SetPath(pcbnew.KIID_PATH("/" + c["uuid"]))
        fp.SetDNP(c["dnp"])
        for k, v in c["fields"].items():
            if k not in ("Footprint", "Description"):
                fp.SetField(k, v)
                fp.GetField(k).SetVisible(False)
        x, y, rot, side = PLACE[ref]
        b.Add(fp)
        if side == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            n = nets.get((ref, pad.GetNumber()))
            if n:
                pad.SetNet(netobj[n])
        rt = fp.Reference()
        rt.SetTextSize(VECTOR2I(MM(0.7), MM(0.7))); rt.SetTextThickness(MM(0.12))
        rt.SetVisible(False)   # tiny board: refs live on Fab layer / assembly drawing
        fp.Value().SetVisible(False)

    for t, x, y, rot, side in SILK:
        tx = pcbnew.PCB_TEXT(b)
        tx.SetText(t); tx.SetPosition(P(x, y))
        tx.SetLayer(pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS)
        tx.SetTextSize(VECTOR2I(MM(0.8), MM(0.8))); tx.SetTextThickness(MM(0.15))
        tx.SetTextAngleDegrees(rot)
        if side == "B":
            tx.SetMirrored(True)
        b.Add(tx)

    t, x, y = CREDIT
    tx = pcbnew.PCB_TEXT(b)
    tx.SetText(t); tx.SetPosition(P(x, y)); tx.SetLayer(pcbnew.B_SilkS)
    tx.SetTextSize(VECTOR2I(MM(1), MM(1))); tx.SetTextThickness(MM(0.2)); tx.SetBold(True)
    tx.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_BOTTOM); tx.SetMirrored(True)
    b.Add(tx)

    outline(b)
    return b, netobj


def route(b):
    tools = os.environ.get("FREEROUTING_DIR", os.path.join(HERE, "tools"))  # dir with freerouting.jar + jre/
    java = glob.glob(os.path.join(tools, "jre", "*", "bin", "java.exe"))[0]
    dsn = os.path.join(HERE, NAME + ".dsn"); ses = os.path.join(HERE, NAME + ".ses")
    if os.path.exists(ses):
        os.remove(ses)
    real = edge_items(b)
    for e in real:
        b.Remove(e)
    outline(b, EDGE_CLR - 0.15)   # router keeps ~0.2 mm clearance from this inset outline (+margin)
    nc = b.GetDesignSettings().m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(MM(0.21))    # margin for Freerouting coordinate rounding
    ok = pcbnew.ExportSpecctraDSN(b, dsn)
    nc.SetClearance(MM(0.2))
    for e in edge_items(b):
        b.Remove(e)
    for e in real:
        b.Add(e)
    assert ok, "DSN export failed"
    r = subprocess.run([java, "-jar", os.path.join(tools, "freerouting.jar"), "-de", dsn, "-do", ses,
                        "-mp", "100", "--gui.enabled=false"], capture_output=True, text=True, timeout=900)
    tail = (r.stdout + r.stderr).strip().splitlines()[-8:]
    print("\n".join(tail))
    assert os.path.exists(ses), "Freerouting produced no SES"
    assert pcbnew.ImportSpecctraSES(b, ses), "SES import failed"
    # drop vias the router left connected on only one layer (GND vias are kept: they stitch the pours)
    tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
    for v in [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]:
        if v.GetNetname() == "/GND":
            continue
        layers = {t.GetLayer() for t in tracks if t.GetNetCode() == v.GetNetCode()
                  and v.GetPosition() in (t.GetStart(), t.GetEnd())}
        if len(layers) < 2:
            b.Remove(v)
    # Freerouting necks tracks down at fine-pitch pads; enforce the board minimum width
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < MM(MIN_TRACK):
            t.SetWidth(MM(MIN_TRACK))


def main():
    b, netobj = build()
    if "--route" in sys.argv:
        route(b)
    zone(b, netobj["/GND"], pcbnew.F_Cu, 0)
    zone(b, netobj["/GND"], pcbnew.B_Cu, 0)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    out = os.path.join(PRJ, NAME + ".kicad_pcb")
    b.Save(out)
    write_rules()
    print("saved", out)


def write_rules():
    import json
    pro = os.path.join(PRJ, NAME + ".kicad_pro")
    d = json.load(open(pro))
    d.setdefault("board", {}).setdefault("design_settings", {})["rules"] = {
        "min_clearance": 0.0, "min_track_width": MIN_TRACK, "min_via_diameter": 0.5,
        "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": EDGE_CLR,
        "min_hole_to_hole": 0.25, "min_via_annular_width": 0.1, "min_hole_clearance": 0.25,
        "min_silk_clearance": 0.0, "min_text_height": 0.8, "min_text_thickness": 0.08}
    d.setdefault("net_settings", {})["classes"] = [{
        "name": "Default", "clearance": 0.2, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3,
        "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
        "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0,
        "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
        "priority": 2147483647}]
    json.dump(d, open(pro, "w"), indent=2)


if __name__ == "__main__":
    main()
