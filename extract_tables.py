#!/usr/bin/env python3
"""Extract all thermodynamic table data from the PDF into JSON."""

import pdfplumber
import json
import re
import os

PDF_PATH = os.path.join(os.path.dirname(__file__), "Thermo Textbook Tables.pdf")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "thermo_data.json")

pdf = pdfplumber.open(PDF_PATH)
pages_text = [page.extract_text() or "" for page in pdf.pages]


def parse_rows(page_indices, min_cols=3):
    rows = []
    skip = ['TABLE', 'Temp', 'Press', 'kJ', 'kPa', 'Enthalpy', 'Entropy', 'Specific',
            'Internal', 'Evap', 'Confirming', 'APPENDIX', 'GTBL', 'PBY', 'Saturated',
            'Superheated', 'Compressed', 'Carbon', 'Ammonia', 'Nitrogen', 'Methane',
            'Thermodynamic', 'Properties', '\u25e6', 'm3/kg', 'R-410', 'R-134', 'Vapor',
            'Liquid', 'Solid', '(continued)', 'Sat.L', 'Sat.V', 'v u', 'h s',
            'Volume', 'Energy']
    for pi in page_indices:
        for line in pages_text[pi].split('\n'):
            line = line.strip()
            if not line or any(kw in line for kw in skip):
                continue
            parts = line.split()
            vals = []
            valid = True
            for p in parts:
                if p in ('\u2014', '\u2212', '-'):
                    vals.append(None)
                else:
                    try:
                        vals.append(float(p))
                    except ValueError:
                        valid = False
                        break
            if valid and len(vals) >= min_cols:
                rows.append(vals)
    return rows


def parse_superheated_pages(page_indices):
    pressure_data = {}
    for pi in page_indices:
        text = pages_text[pi]
        lines = text.split('\n')
        pressures = []
        for line in lines:
            matches = re.findall(r'(\d+\.?\d*)\s*kPa\s*\(', line)
            for m in matches:
                p = float(m)
                if p not in pressures:
                    pressures.append(p)
        if len(pressures) < 2:
            for line in lines:
                matches = re.findall(r'(\d+)\s*kPa', line)
                for m in matches:
                    p = float(m)
                    if p not in pressures:
                        pressures.append(p)
        p1 = pressures[0] if len(pressures) >= 1 else None
        p2 = pressures[1] if len(pressures) >= 2 else None
        if not p1:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            skip_kw = ['TABLE', 'Temp', 'Press', 'kJ', 'kPa', 'Enthalpy', 'Entropy',
                       'Specific', 'APPENDIX', 'GTBL', 'PBY', 'Superheated', 'Vapor',
                       '\u25e6', 'm3/kg', '(continued)', 'Volume', 'Confirming', '=',
                       'Compressed', 'Liquid', 'Carbon', 'Ammonia', 'Nitrogen', 'Methane',
                       'Thermodynamic', 'Properties', 'R-410', 'R-134', 'Internal', 'Energy']
            if any(kw in line for kw in skip_kw):
                continue
            parts = line.split()
            vals = []
            valid = True
            is_sat = False
            for pv in parts:
                if pv in ('\u2014', '\u2212'):
                    vals.append(None)
                elif pv == 'Sat.':
                    is_sat = True
                else:
                    try:
                        vals.append(float(pv))
                    except ValueError:
                        valid = False
                        break
            if not valid:
                continue
            if is_sat:
                t_val = "Sat"
            elif len(vals) >= 5:
                t_val = vals[0]
                vals = vals[1:]
            else:
                continue
            if len(vals) >= 4 and vals[0] is not None:
                if p1 not in pressure_data:
                    pressure_data[p1] = []
                pressure_data[p1].append({"T": t_val, "v": vals[0], "u": vals[1], "h": vals[2], "s": vals[3]})
            if p2 and len(vals) >= 8 and vals[4] is not None:
                if p2 not in pressure_data:
                    pressure_data[p2] = []
                pressure_data[p2].append({"T": t_val, "v": vals[4], "u": vals[5], "h": vals[6], "s": vals[7]})
    return pressure_data


def format_superheated(data):
    result = {}
    for p, rows in sorted(data.items()):
        result[str(p)] = rows
    return result


# B.1.1: Saturated Water - Temperature Entry
hs_low = parse_rows([0], 8)
vu_high = parse_rows([1], 8)
hs_high = parse_rows([2], 8)
b11 = []
for r in hs_low:
    b11.append({"T": r[0], "P": r[1], "hf": r[2], "hfg": r[3], "hg": r[4],
                "sf": r[5], "sfg": r[6], "sg": r[7]})
for i, r in enumerate(vu_high):
    entry = {"T": r[0], "P": r[1], "vf": r[2], "vfg": r[3], "vg": r[4],
             "uf": r[5], "ufg": r[6], "ug": r[7]}
    if i < len(hs_high):
        h = hs_high[i]
        entry.update({"hf": h[2], "hfg": h[3], "hg": h[4], "sf": h[5], "sfg": h[6], "sg": h[7]})
    b11.append(entry)

# B.1.2: Saturated Water - Pressure Entry
vu_p = parse_rows([3, 5], 8)
hs_p = parse_rows([4, 6], 8)
b12 = []
hs_map = {r[0]: r for r in hs_p}
for r in vu_p:
    entry = {"P": r[0], "T": r[1], "vf": r[2], "vfg": r[3], "vg": r[4],
             "uf": r[5], "ufg": r[6], "ug": r[7]}
    if r[0] in hs_map:
        h = hs_map[r[0]]
        entry.update({"hf": h[2], "hfg": h[3], "hg": h[4], "sf": h[5], "sfg": h[6], "sg": h[7]})
    b12.append(entry)

# B.1.3: Superheated Water
b13 = format_superheated(parse_superheated_pages(range(7, 13)))

# B.1.4: Compressed Liquid Water
b14 = format_superheated(parse_superheated_pages(range(13, 15)))

# B.1.5: Saturated Solid-Vapor Water
vu_sv = parse_rows([15], 8)
hs_sv = parse_rows([16], 8)
b15 = []
hs_map_sv = {r[0]: r for r in hs_sv}
for r in vu_sv:
    entry = {"T": r[0], "P": r[1], "vi": r[2], "vig": r[3], "vg": r[4],
             "ui": r[5], "uig": r[6], "ug": r[7]}
    if r[0] in hs_map_sv:
        h = hs_map_sv[r[0]]
        entry.update({"hi": h[2], "hig": h[3], "hg": h[4], "si": h[5], "sig": h[6], "sg": h[7]})
    b15.append(entry)

# B.2.1: Saturated Ammonia
vu_amm = parse_rows([17], 8)
hs_amm = parse_rows([18], 8)
b21 = []
hs_map_amm = {r[0]: r for r in hs_amm}
for r in vu_amm:
    entry = {"T": r[0], "P": r[1], "vf": r[2], "vfg": r[3], "vg": r[4],
             "uf": r[5], "ufg": r[6], "ug": r[7]}
    if r[0] in hs_map_amm:
        h = hs_map_amm[r[0]]
        entry.update({"hf": h[2], "hfg": h[3], "hg": h[4], "sf": h[5], "sfg": h[6], "sg": h[7]})
    b21.append(entry)

# B.2.2: Superheated Ammonia
b22 = format_superheated(parse_superheated_pages(range(19, 23)))

# B.3.1: Saturated CO2
vu_co2 = parse_rows([23], 8)
hs_co2 = parse_rows([24], 8)
b31 = []
hs_map_co2 = {r[0]: r for r in hs_co2}
for r in vu_co2:
    entry = {"T": r[0], "P": r[1], "vf": r[2], "vfg": r[3], "vg": r[4],
             "uf": r[5], "ufg": r[6], "ug": r[7]}
    if r[0] in hs_map_co2:
        h = hs_map_co2[r[0]]
        entry.update({"hf": h[2], "hfg": h[3], "hg": h[4], "sf": h[5], "sfg": h[6], "sg": h[7]})
    b31.append(entry)

# B.3.2: Superheated CO2
b32 = format_superheated(parse_superheated_pages(range(25, 27)))

# B.4.1: Saturated R-410a
vu_r410 = parse_rows([27], 8)
hs_r410 = parse_rows([28], 8)
b41 = []
hs_map_r410 = {r[0]: r for r in hs_r410}
for r in vu_r410:
    entry = {"T": r[0], "P": r[1], "vf": r[2], "vfg": r[3], "vg": r[4],
             "uf": r[5], "ufg": r[6], "ug": r[7]}
    if r[0] in hs_map_r410:
        h = hs_map_r410[r[0]]
        entry.update({"hf": h[2], "hfg": h[3], "hg": h[4], "sf": h[5], "sfg": h[6], "sg": h[7]})
    b41.append(entry)

# B.4.2: Superheated R-410a
b42 = format_superheated(parse_superheated_pages(range(29, 33)))

# B.5.1: Saturated R-134a
vu_r134 = parse_rows([33], 8)
hs_r134 = parse_rows([34], 8)
b51 = []
hs_map_r134 = {r[0]: r for r in hs_r134}
for r in vu_r134:
    entry = {"T": r[0], "P": r[1], "vf": r[2], "vfg": r[3], "vg": r[4],
             "uf": r[5], "ufg": r[6], "ug": r[7]}
    if r[0] in hs_map_r134:
        h = hs_map_r134[r[0]]
        entry.update({"hf": h[2], "hfg": h[3], "hg": h[4], "sf": h[5], "sfg": h[6], "sg": h[7]})
    b51.append(entry)

# B.5.2: Superheated R-134a
b52 = format_superheated(parse_superheated_pages(range(35, 39)))

# B.6.1: Saturated Nitrogen
vu_n2 = parse_rows([39], 8)
b61 = []
for r in vu_n2:
    b61.append({"T": r[0], "P": r[1], "vf": r[2], "vfg": r[3], "vg": r[4],
                "uf": r[5], "ufg": r[6], "ug": r[7]})

# B.6.2: Superheated Nitrogen
b62 = format_superheated(parse_superheated_pages(range(40, 43)))

# B.7.1: Saturated Methane
vu_ch4 = parse_rows([43], 8)
hs_ch4 = parse_rows([44], 8)
b71 = []
hs_map_ch4 = {r[0]: r for r in hs_ch4}
for r in vu_ch4:
    entry = {"T": r[0], "P": r[1], "vf": r[2], "vfg": r[3], "vg": r[4],
             "uf": r[5], "ufg": r[6], "ug": r[7]}
    if r[0] in hs_map_ch4:
        h = hs_map_ch4[r[0]]
        entry.update({"hf": h[2], "hfg": h[3], "hg": h[4], "sf": h[5], "sfg": h[6], "sg": h[7]})
    b71.append(entry)

# B.7.2: Superheated Methane
b72 = format_superheated(parse_superheated_pages(range(45, 48)))

# Assemble full dataset
data = {
    "tables": {
        "B.1.1": {
            "name": "Saturated Water \u2014 Temperature Entry",
            "substance": "Water",
            "type": "saturated",
            "lookup_key": "T",
            "lookup_unit": "\u00b0C",
            "columns": ["T", "P", "vf", "vfg", "vg", "uf", "ufg", "ug", "hf", "hfg", "hg", "sf", "sfg", "sg"],
            "units": ["\u00b0C", "kPa", "m\u00b3/kg", "m\u00b3/kg", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg",
                      "kJ/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K", "kJ/kg\u00b7K", "kJ/kg\u00b7K"],
            "data": b11
        },
        "B.1.2": {
            "name": "Saturated Water \u2014 Pressure Entry",
            "substance": "Water",
            "type": "saturated",
            "lookup_key": "P",
            "lookup_unit": "kPa",
            "columns": ["P", "T", "vf", "vfg", "vg", "uf", "ufg", "ug", "hf", "hfg", "hg", "sf", "sfg", "sg"],
            "units": ["kPa", "\u00b0C", "m\u00b3/kg", "m\u00b3/kg", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg",
                      "kJ/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K", "kJ/kg\u00b7K", "kJ/kg\u00b7K"],
            "data": b12
        },
        "B.1.3": {
            "name": "Superheated Water Vapor",
            "substance": "Water",
            "type": "superheated",
            "columns": ["T", "v", "u", "h", "s"],
            "units": ["\u00b0C", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K"],
            "pressures": b13
        },
        "B.1.4": {
            "name": "Compressed Liquid Water",
            "substance": "Water",
            "type": "superheated",
            "columns": ["T", "v", "u", "h", "s"],
            "units": ["\u00b0C", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K"],
            "pressures": b14
        },
        "B.1.5": {
            "name": "Saturated Solid\u2013Saturated Vapor Water",
            "substance": "Water",
            "type": "saturated",
            "lookup_key": "T",
            "lookup_unit": "\u00b0C",
            "columns": ["T", "P", "vi", "vig", "vg", "ui", "uig", "ug", "hi", "hig", "hg", "si", "sig", "sg"],
            "units": ["\u00b0C", "kPa", "m\u00b3/kg", "m\u00b3/kg", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg",
                      "kJ/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K", "kJ/kg\u00b7K", "kJ/kg\u00b7K"],
            "data": b15
        },
        "B.2.1": {
            "name": "Saturated Ammonia",
            "substance": "Ammonia",
            "type": "saturated",
            "lookup_key": "T",
            "lookup_unit": "\u00b0C",
            "columns": ["T", "P", "vf", "vfg", "vg", "uf", "ufg", "ug", "hf", "hfg", "hg", "sf", "sfg", "sg"],
            "units": ["\u00b0C", "kPa", "m\u00b3/kg", "m\u00b3/kg", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg",
                      "kJ/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K", "kJ/kg\u00b7K", "kJ/kg\u00b7K"],
            "data": b21
        },
        "B.2.2": {
            "name": "Superheated Ammonia",
            "substance": "Ammonia",
            "type": "superheated",
            "columns": ["T", "v", "u", "h", "s"],
            "units": ["\u00b0C", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K"],
            "pressures": b22
        },
        "B.3.1": {
            "name": "Saturated Carbon Dioxide",
            "substance": "CO\u2082",
            "type": "saturated",
            "lookup_key": "T",
            "lookup_unit": "\u00b0C",
            "columns": ["T", "P", "vf", "vfg", "vg", "uf", "ufg", "ug", "hf", "hfg", "hg", "sf", "sfg", "sg"],
            "units": ["\u00b0C", "kPa", "m\u00b3/kg", "m\u00b3/kg", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg",
                      "kJ/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K", "kJ/kg\u00b7K", "kJ/kg\u00b7K"],
            "data": b31
        },
        "B.3.2": {
            "name": "Superheated Carbon Dioxide",
            "substance": "CO\u2082",
            "type": "superheated",
            "columns": ["T", "v", "u", "h", "s"],
            "units": ["\u00b0C", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K"],
            "pressures": b32
        },
        "B.4.1": {
            "name": "Saturated R-410a",
            "substance": "R-410a",
            "type": "saturated",
            "lookup_key": "T",
            "lookup_unit": "\u00b0C",
            "columns": ["T", "P", "vf", "vfg", "vg", "uf", "ufg", "ug", "hf", "hfg", "hg", "sf", "sfg", "sg"],
            "units": ["\u00b0C", "kPa", "m\u00b3/kg", "m\u00b3/kg", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg",
                      "kJ/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K", "kJ/kg\u00b7K", "kJ/kg\u00b7K"],
            "data": b41
        },
        "B.4.2": {
            "name": "Superheated R-410a",
            "substance": "R-410a",
            "type": "superheated",
            "columns": ["T", "v", "u", "h", "s"],
            "units": ["\u00b0C", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K"],
            "pressures": b42
        },
        "B.5.1": {
            "name": "Saturated R-134a",
            "substance": "R-134a",
            "type": "saturated",
            "lookup_key": "T",
            "lookup_unit": "\u00b0C",
            "columns": ["T", "P", "vf", "vfg", "vg", "uf", "ufg", "ug", "hf", "hfg", "hg", "sf", "sfg", "sg"],
            "units": ["\u00b0C", "kPa", "m\u00b3/kg", "m\u00b3/kg", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg",
                      "kJ/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K", "kJ/kg\u00b7K", "kJ/kg\u00b7K"],
            "data": b51
        },
        "B.5.2": {
            "name": "Superheated R-134a",
            "substance": "R-134a",
            "type": "superheated",
            "columns": ["T", "v", "u", "h", "s"],
            "units": ["\u00b0C", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K"],
            "pressures": b52
        },
        "B.6.1": {
            "name": "Saturated Nitrogen",
            "substance": "Nitrogen",
            "type": "saturated",
            "lookup_key": "T",
            "lookup_unit": "K",
            "columns": ["T", "P", "vf", "vfg", "vg", "uf", "ufg", "ug"],
            "units": ["K", "kPa", "m\u00b3/kg", "m\u00b3/kg", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg"],
            "data": b61
        },
        "B.6.2": {
            "name": "Superheated Nitrogen",
            "substance": "Nitrogen",
            "type": "superheated",
            "columns": ["T", "v", "u", "h", "s"],
            "units": ["K", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K"],
            "pressures": b62
        },
        "B.7.1": {
            "name": "Saturated Methane",
            "substance": "Methane",
            "type": "saturated",
            "lookup_key": "T",
            "lookup_unit": "K",
            "columns": ["T", "P", "vf", "vfg", "vg", "uf", "ufg", "ug", "hf", "hfg", "hg", "sf", "sfg", "sg"],
            "units": ["K", "kPa", "m\u00b3/kg", "m\u00b3/kg", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg",
                      "kJ/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K", "kJ/kg\u00b7K", "kJ/kg\u00b7K"],
            "data": b71
        },
        "B.7.2": {
            "name": "Superheated Methane",
            "substance": "Methane",
            "type": "superheated",
            "columns": ["T", "v", "u", "h", "s"],
            "units": ["K", "m\u00b3/kg", "kJ/kg", "kJ/kg", "kJ/kg\u00b7K"],
            "pressures": b72
        }
    }
}

with open(OUTPUT_PATH, 'w') as f:
    json.dump(data, f, indent=2)

print(f"Extracted data saved to {OUTPUT_PATH}")
for tid, tinfo in data["tables"].items():
    if tinfo["type"] == "saturated":
        print(f"  {tid}: {tinfo['name']} - {len(tinfo['data'])} rows")
    else:
        print(f"  {tid}: {tinfo['name']} - {len(tinfo['pressures'])} pressure levels")
