"""FreeCAD GUI macro: renders enclosure previews into docs/. Run:  freecad.exe tools\render_enclosure.py"""
import os, sys
os.environ["ENC_NO_MAIN"] = "1"
HERE = r"C:\Users\dasukim\Desktop\Kicad\Moisture Sensor\tools"
sys.path.insert(0, HERE)
import FreeCAD as App, FreeCADGui as Gui, Part
from FreeCAD import Vector as V
import gen_enclosure as G
D = os.path.join(G.ROOT, "docs")
body, lid, door = G.make_body(), G.make_lid(), G.make_door()
pcb = G.pcb_shape(); dm = G.dummies()
print("PCB bbox", pcb.BoundBox)
doc = App.newDocument("enc")
COL = dict(body=(0.29,0.56,0.85), lid=(0.62,0.77,0.94), door=(0.94,0.63,0.19), pcb=(0.1,0.48,0.23),
           oled=(0.1,0.1,0.1), cells=(0.8,0.8,0.8), button=(0.82,0.19,0.19))
objs, BASE = {}, {}
for n, s in dict(body=body, lid=lid, door=door, pcb=pcb, **dm).items():
    o = doc.addObject("Part::Feature", n); o.Shape = s; objs[n] = o; BASE[n] = o.Placement.copy()
doc.recompute()
for n, o in objs.items():
    o.ViewObject.ShapeColor = COL[n]
    o.ViewObject.LineColor = (0.15, 0.15, 0.15)
Gui.SendMsgToActiveView("ViewFit"); Gui.SendMsgToActiveView("OrthographicCamera")
v = Gui.ActiveDocument.ActiveView
def shot(name, show, place={}, view="iso", w=1400, h=1000):
    for n, o in objs.items():
        o.ViewObject.Visibility = n in show
        o.Placement = App.Placement(V(*place.get(n, (0, 0, 0))), App.Rotation()).multiply(BASE[n])
    getattr(v, {"iso": "viewIsometric", "top": "viewTop", "bottom": "viewBottom", "rear": "viewRear",
                "front": "viewFront", "left": "viewLeft", "right": "viewRight"}[view])()
    if isinstance(view, str) and view == "iso2":
        pass
    v.fitAll()
    v.saveImage(os.path.join(D, name), w, h, "White")
ALL = list(objs)
shot("enc_exploded.png", ALL, {"lid": (0, 0, 35), "door": (0, -30, 55)}, "iso")
shot("enc_inside.png", ["body", "pcb", "oled", "cells", "button"], {}, "top")
shot("enc_front.png", ["body", "lid", "door", "oled", "button"], {}, "bottom")
shot("enc_lid_under.png", ["lid"], {}, "bottom")
def cam(name, show, rot, place={}):
    for n, o in objs.items():
        o.ViewObject.Visibility = n in show
        o.Placement = App.Placement(V(*place.get(n, (0, 0, 0))), App.Rotation()).multiply(BASE[n])
    v.setCameraOrientation(rot); v.fitAll(); v.saveImage(os.path.join(D, name), 1400, 1000, "White")
try:
    # display side, 3/4 view (looking at -Z face from below, tilted)
    r = App.Rotation(V(1, 0, 0), 180).multiply(App.Rotation(V(1, 0, 0), -35)).multiply(App.Rotation(V(0, 0, 1), 25))
    cam("enc_front34.png", ["body", "lid", "door", "oled", "button"], App.Rotation(V(0,0,1),-25).multiply(App.Rotation(V(1,0,0),145)))
    cam("enc_back34.png", ["body", "lid", "door", "button"], App.Rotation(V(0,0,1),25).multiply(App.Rotation(V(1,0,0),40)))
    cam("enc_door_open.png", ["body", "lid", "door", "cells", "button"], App.Rotation(V(0,0,1),25).multiply(App.Rotation(V(1,0,0),40)), {"door": (0, -40, 0)})
except Exception as e:
    print("cam failed", e)
App.closeDocument("enc")
os._exit(0)