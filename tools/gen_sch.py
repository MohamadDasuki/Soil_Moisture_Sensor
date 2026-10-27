import uuid, json, os, datetime
from sexp import *

OUT = r"C:\Users\dasukim\Desktop\Kicad\Moisture Sensor"
PROJ = "Moisture_Sensor"
ROOT = str(uuid.uuid5(uuid.NAMESPACE_DNS, "moisture-sensor-root"))
_n = [0]


def U(key=None):
    _n[0] += 1
    return str(uuid.uuid5(uuid.UUID(ROOT), key or ("n%d" % _n[0])))

# (ref, lib, name, value, footprint, x, y, {pin: net or None(=NC)}, extra props, dnp)
FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C6 = "Capacitor_SMD:C_0603_1608Metric"
FP_C8 = "Capacitor_SMD:C_0805_2012Metric"
parts = [
    # --- Power input ---
    ("J5", "Connector_Generic", "Conn_01x02", "BATTERY 3xAAA", "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical",
     40, 60, {"1": "BAT_RAW", "2": "GND"},
     {"MPN": "B2B-PH-K-S(LF)(SN)", "Manufacturer": "JST", "LCSC": "C131337", "Note": "3xAAA holder (3.0-4.8V) with JST-PH leads, in case (pin1 = +)"}, False),
    ("Q1", "Transistor_FET", "Q_PMOS_GSD", "AO3401A", "Package_TO_SOT_SMD:SOT-23",
     80, 60, {"1": "GND", "2": "VBAT", "3": "BAT_RAW"},
     {"MPN": "AO3401A", "Manufacturer": "Alpha & Omega", "LCSC": "C15127", "Note": "Reverse-polarity protection"}, False),
    ("C1", "Device", "C", "10uF 25V X5R", FP_C8, 105, 60, {"1": "VBAT", "2": "GND"},
     {"MPN": "CL21A106KAYNNNE", "Manufacturer": "Samsung", "LCSC": "C15850"}, False),
    ("C2", "Device", "C", "100nF", FP_C6, 130, 60, {"1": "VBAT", "2": "GND"},
     {"MPN": "CC0603KRX7R9BB104", "Manufacturer": "Yageo", "LCSC": "C14663"}, False),
    ("#FLG01", "power", "PWR_FLAG", "PWR_FLAG", "", 155, 52, {"1": "VBAT"}, {}, False),
    ("#FLG02", "power", "PWR_FLAG", "PWR_FLAG", "", 180, 52, {"1": "GND"}, {}, False),
    # --- MCU ---
    ("U1", "MCU_Microchip_ATtiny", "ATtiny1614-SS", "ATtiny1614-SSNR", None, 200, 130,
     {"1": "VBAT", "14": "GND", "10": "UPDI", "2": "LOAD_EN", "3": "AOUT", "4": "BTN",
      "9": "SCL", "8": "SDA",
      "11": None, "12": None, "13": None, "5": None, "6": None, "7": None},
     {"MPN": "ATTINY1614-SSNR", "Manufacturer": "Microchip", "LCSC": "C481364"}, False),
    ("J1", "Connector_Generic", "Conn_01x03", "UPDI", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     150, 175, {"1": "UPDI", "2": "GND", "3": "VBAT"},
     {"Note": "UPDI through-hole pads on board edge; plug Dupont wires / temporary header (3.3V SerialUPDI)"}, True),
    ("SW1", "Connector_Generic", "Conn_01x02", "READ BUTTON", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
         260, 175, {"1": "BTN", "2": "GND"},
         {"MPN": "PBS-110-XBK", "Manufacturer": "Twidec", "Note": "7mm panel-mount momentary NO pushbutton, leads soldered to pads"}, False),
    # --- Switched peripheral rail ---
    ("U2", "Power_Management", "TPS22917DBV", "TPS22917DBVR", None, 70, 140,
     {"1": "VBAT", "2": "GND", "3": "LOAD_EN", "4": "CT", "5": "QOD", "6": "VSW"},
     {"MPN": "TPS22917DBVR", "Manufacturer": "Texas Instruments", "LCSC": "C2681320"}, False),
    ("R3", "Device", "R", "0R", FP_R, 95, 160, {"1": "QOD", "2": "VSW"},
     {"MPN": "0603WAF0000T5E", "Manufacturer": "UNI-ROYAL", "LCSC": "C21189", "Note": "Quick output discharge (QOD->VOUT)"}, False),
    ("C3", "Device", "C", "1nF", FP_C6, 40, 165, {"1": "CT", "2": "GND"},
     {"MPN": "CL10B102KB8NNNC", "Manufacturer": "Samsung", "LCSC": "C1588", "Note": "Load switch slew-rate"}, False),
    ("C4", "Device", "C", "22uF 25V X5R", FP_C8, 105, 140, {"1": "VSW", "2": "GND"},
     {"MPN": "CL21A226MAQNNNE", "Manufacturer": "Samsung", "LCSC": "C45783"}, False),
    ("C5", "Device", "C", "100nF", FP_C6, 130, 140, {"1": "VSW", "2": "GND"},
     {"MPN": "CC0603KRX7R9BB104", "Manufacturer": "Yageo", "LCSC": "C14663"}, False),
    ("C6", "Device", "C", "100nF", FP_C6, 150, 140, {"1": "VBAT", "2": "GND"},
     {"MPN": "CC0603KRX7R9BB104", "Manufacturer": "Yageo", "LCSC": "C14663"}, False),
    # --- I2C pull-ups ---
    ("R1", "Device", "R", "10k", FP_R, 270, 60, {"1": "VSW", "2": "SCL"},
     {"MPN": "0603WAF1002T5E", "Manufacturer": "UNI-ROYAL", "LCSC": "C25804"}, False),
    ("R2", "Device", "R", "10k", FP_R, 285, 60, {"1": "VSW", "2": "SDA"},
     {"MPN": "0603WAF1002T5E", "Manufacturer": "UNI-ROYAL", "LCSC": "C25804"}, False),
    # --- External connectors ---
    ("J2", "Connector_Generic", "Conn_01x04",     "OLED SSD1306 0.96in", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
         330, 70, {"1": "GND", "2": "VSW", "3": "SCL", "4": "SDA"},
         {"MPN": "Supplied Dupont wires soldered to pads (opt. 1x04 2.54mm header)", "Manufacturer": "-", "Note": "ELEGOO 0.96in SSD1306 module, pin order GND-VCC-SCL-SDA"}, False),
    ("J3", "Connector_Generic", "Conn_01x03", "SOIL SENSOR v1.2", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     330, 110, {"1": "GND", "2": "VSW", "3": "AOUT"},
     {"MPN": "Supplied PH2.0-3P to Dupont cable soldered to pads", "Manufacturer": "DIYmall", "Note": "Capacitive soil sensor v1.2, analog 0-3V, GND-VCC-AOUT; bypass its 662K LDO"}, False),
]

notes = [
    (30, 25, "Button-activated Soil Moisture Meter  -  3xAAA (3.0-4.8V), no regulator\n"
             "Idle: MCU in power-down, TPS22917 off -> ~0.5 uA total.  Press SW1 -> PA6 wakes MCU ->\n"
             "LOAD_EN high -> VSW powers OLED + sensor -> ADC reads AOUT (PA5) -> display 15 s -> LOAD_EN low -> sleep."),
    (30, 200, "Firmware notes: run at 10 MHz (valid >2.7 V). Before LOAD_EN low, disable TWI and set\n"
              "PB0/PB1 to input w/o pull-up so the unpowered OLED/sensor aren't back-fed.\n"
              "Sensor read ratiometric (ADC ref = VDD, sensor LDO bypassed). Battery: VDD vs. internal reference.\n"
              "OLED module runs from VSW via its own LDO (3.3-5V). Low-batt cutoff ~3.3 V (1.1 V/cell)."),
]

libcache, used = {}, {}


def fx(x):
    return round(x / 1.27) * 1.27


def prop(name, val, x, y, hide=False, ang=0, justify=None):
    p = [Sym("property"), name, val, [Sym("at"), x, y, ang]]
    if hide:
        p.append([Sym("hide"), Sym("yes")])
    eff = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
    if justify:
        eff.append([Sym("justify")] + [Sym(j) for j in justify])
    p.append(eff)
    return p


body = []
lib_symbols = []
for ref, lib, name, val, fp, x, y, conns, extra, dnp in parts:
    lid = f"{lib}:{name}"
    if lid not in libcache:
        sd = lib_symbol(lib, name)
        libcache[lid] = sd
        emb = copy.deepcopy(sd)
        emb[1] = lid
        lib_symbols.append(emb)
    sd = libcache[lid]
    x, y = fx(x), fx(y)
    pd = pins(sd)
    if fp is None:
        fp = next(p[2] for p in find(sd, "property") if p[1] == "Footprint")
    ds = next((p[2] for p in find(sd, "property") if p[1] == "Datasheet"), "")
    xs = [v[0] for v in pd.values()]
    ys = [-v[1] for v in pd.values()]
    is_power = ref.startswith("#")
    if all(abs(v) < 0.01 for v in xs) or (max(xs) - min(xs) < 10 and not ref.startswith(("SW", "#", "J"))):
        sx = x + max(xs) + (3.81 if max(xs) > 0 else 2.54)
        rpos, vpos, just = (sx, y - 1.27), (sx, y + 1.27), ["left"]
    else:
        rpos, vpos, just = (x, y + min(ys) - 2.54), (x, y + max(ys) + 2.54), None
        if ref.startswith("J"):
            rpos, vpos = (x + 1.27, y + min(ys) - 2.54), (x + 1.27, y + max(ys) + 2.54)
    s = [Sym("symbol"), [Sym("lib_id"), lid], [Sym("at"), x, y, 0], [Sym("unit"), 1],
         [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("no" if is_power else "yes")],
         [Sym("on_board"), Sym("no" if is_power else "yes")], [Sym("dnp"), Sym("yes" if dnp else "no")],
         [Sym("uuid"), U("sym:" + ref)],
         prop("Reference", ref, *rpos, hide=is_power, justify=just),
         prop("Value", val, *vpos, justify=just),
         prop("Footprint", fp, x, y, hide=True),
         prop("Datasheet", ds, x, y, hide=True)]
    for k, v in extra.items():
        s.append(prop(k, v, x, y, hide=True))
    for num in pd:
        s.append([Sym("pin"), num, [Sym("uuid"), U()]])
    s.append([Sym("instances"), [Sym("project"), PROJ,
              [Sym("path"), "/" + ROOT, [Sym("reference"), ref], [Sym("unit"), 1]]]])
    body.append(s)

    missing = set(pd) - set(conns)
    assert not missing, f"{ref} unassigned pins {missing}"
    for num, net in conns.items():
        px, py, rot, _, _ = pd[num]
        ax, ay = x + px, y - py
        if net is None:
            body.append([Sym("no_connect"), [Sym("at"), ax, ay], [Sym("uuid"), U()]])
            continue
        ang = {0: 180, 180: 0, 90: 270, 270: 90}[rot]
        j = ["left", "bottom"] if ang in (0, 90) else ["right", "bottom"]
        body.append([Sym("label"), net, [Sym("at"), ax, ay, ang],
                     [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("justify")] + [Sym(t) for t in j]],
                     [Sym("uuid"), U()]])

for x, y, t in notes:
    body.append([Sym("text"), t, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), x, y, 0],
                 [Sym("effects"), [Sym("font"), [Sym("size"), 1.524, 1.524]], [Sym("justify"), Sym("left"), Sym("top")]],
                 [Sym("uuid"), U()]])

sch = [Sym("kicad_sch"), [Sym("version"), Sym("20250610")], [Sym("generator"), "eeschema"],
       [Sym("generator_version"), "9.99"], [Sym("uuid"), ROOT], [Sym("paper"), "A3"],
       [Sym("title_block"), [Sym("title"), "Soil Moisture Meter"], [Sym("date"), datetime.date.today().isoformat()],
        [Sym("rev"), "A"], [Sym("comment"), Sym("1"), "2xAAA, ATtiny1614, TPS22917 load switch, SSD1306 OLED, STEMMA soil sensor"]],
       [Sym("lib_symbols")] + lib_symbols] + body + \
      [[Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]]]

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, PROJ + ".kicad_sch"), "w", encoding="utf-8", newline="\n") as f:
    f.write(dump(sch) + "\n")
pro = os.path.join(OUT, PROJ + ".kicad_pro")
if not os.path.exists(pro):
    with open(pro, "w") as f:
        json.dump({"meta": {"filename": PROJ + ".kicad_pro", "version": 3}}, f, indent=2)
print("wrote", OUT)
