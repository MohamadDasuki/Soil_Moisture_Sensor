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

W, H = 27.8, 17.0          # board size (mm)
OX, OY = 100.0, 100.0      # board origin on the page
R_CORNER = 1.0

# ref: (x, y, rot_deg, side)   coordinates relative to board top-left
PLACE = {
    "J2": (1.8, 1.6, 90, "F"),        # OLED 2.54mm pads, pin1 left: GND VCC SCL SDA
    "J3": (W - 4.2, 3.4, 180, "F"),   # soil sensor (cable exits top edge)
    "U2": (15.3, 2.2, 0, "F"),
    "C6": (12.2, 2.2, 90, "F"),
    "C4": (18.4, 2.2, 90, "F"),
    "C5": (12.2, 5.6, 90, "F"),
    "C3": (17.0, 5.6, 90, "F"),
    "C2": (14.6, 5.6, 90, "F"),
    "J5": (2.8, 9.6, 0, "F"),         # battery JST-PH, vertical
    "Q1": (2.3, 15.0, 0, "F"),
    "C1": (5.8, 15.0, 90, "F"),
    "U1": (14.4, 12.2, 0, "F"),
    "R1": (19.8, 9.0, 90, "F"),
    "R2": (21.6, 9.0, 90, "F"),
    "R3": (23.4, 9.0, 90, "F"),
    "SW1": (23.4, 14.6, 0, "F"),
    "J1": (23.4, 9.5, 0, "B"),        # UPDI pads on bottom
}

SILK = [  # (text, x, y, rot, side)
    ("OLED", 5.6, 4.6, 0, "B"),
    ("G", 1.8, 3.9, 0, "F"), ("V", 4.34, 3.9, 0, "F"), ("C", 6.88, 3.9, 0, "F"), ("D", 9.42, 3.9, 0, "F"),
    ("SENSOR", W - 4.2, 0.9, 0, "B"),
    ("BATT", 3.8, 12.6, 0, "B"),
    ("UPDI", 23.4, 15.6, 0, "B"),
    ("SOIL METER rB", 15.3, 15.8, 0, "B"),
]


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


def outline(b):
    r = R_CORNER
    add_line(b, P(r, 0), P(W - r, 0)); add_line(b, P(W, r), P(W, H - r))
    add_line(b, P(W - r, H), P(r, H)); add_line(b, P(0, H - r), P(0, r))
    add_arc(b, P(W - r, r), P(W - r, 0), 90)
    add_arc(b, P(W - r, H - r), P(W, H - r), 90)
    add_arc(b, P(r, H - r), P(r, H), 90)
    add_arc(b, P(r, r), P(0, r), 90)


def zone(b, net, layer, prio):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer); z.SetNet(net); z.SetAssignedPriority(prio)
    z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2))
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)   # SMD pads solid; TH connectors get thermals (below)
    ol = z.Outline(); ol.NewOutline()
    i, c = 0.4, 1.2   # inset from edge, chamfer to clear the rounded corners
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
    ds.m_TrackMinWidth = MM(0.15); ds.m_MinClearance = MM(0.15)
    ds.m_ViasMinSize = MM(0.5); ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(0.25)
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
        if ref in ("J2", "J5"):
            fp.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
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

    outline(b)
    return b, netobj


def route(b):
    tools = os.path.join(HERE, "tools")
    java = glob.glob(os.path.join(tools, "jre", "*", "bin", "java.exe"))[0]
    dsn = os.path.join(HERE, NAME + ".dsn"); ses = os.path.join(HERE, NAME + ".ses")
    if os.path.exists(ses):
        os.remove(ses)
    assert pcbnew.ExportSpecctraDSN(b, dsn), "DSN export failed"
    r = subprocess.run([java, "-jar", os.path.join(tools, "freerouting.jar"), "-de", dsn, "-do", ses,
                        "-mp", "40", "--gui.enabled=false"], capture_output=True, text=True, timeout=900)
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
        "min_clearance": 0.15, "min_track_width": 0.12, "min_via_diameter": 0.5,
        "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.25,
        "min_hole_to_hole": 0.25, "min_via_annular_width": 0.1, "min_hole_clearance": 0.2,
        "min_silk_clearance": 0.0, "min_text_height": 0.6, "min_text_thickness": 0.1}
    d.setdefault("net_settings", {})["classes"] = [{
        "name": "Default", "clearance": 0.2, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3,
        "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
        "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0,
        "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
        "priority": 2147483647}]
    json.dump(d, open(pro, "w"), indent=2)


if __name__ == "__main__":
    main()
