fixes = {
    "AOR": (1448, 1576), "ASC": (24379, 24541), "BKP": (1450, 1701),
    "BKT": (1449, 1661), "BST": (2765, 3020), "CES": (1467, 2278),
    "DCR": (1446, 1525), "DP": (1432, 1430), "DRM": (1468, 2295),
    "DS": (1426, 1429), "EPO": (1438, 1424), "EVO": (1455, 1842),
    "FCO": (1452, 1780), "FFI": (1443, 1481), "FLF": (1442, 1464),
    "G1": (1420, 1441), "G2": (1421, 1440), "GEN": (1451, 1728),
    "HIF": (2110, 2480), "MEG": (24377, 24380), "MT": (1433, 1368),
    "N2": (1422, 1434), "N4": (1424, 1444), "PFL": (24378, 24448),
    "PHF": (1444, 1494), "POR": (24380, 24587), "PRC": (1445, 1509),
    "ROS": (1447, 1534), "RR": (1367, 1428), "SHF": (2747, 2754),
    "STS": (1454, 1815),
}
missing = {
    "BS2": 605, "BSS": 1663, "CCC": 2931, "CHP": 2685, "CLB": 2867,
    "CoL": 1415, "HIFSV": 2594, "MEW": 23237, "OBF": 23228, "PAF": 23353,
    "PAL": 23120, "PAR": 23286, "SHL": 2054, "SM01": 1863, "SM02": 1919,
    "SM03": 1957, "SM04": 2071, "SM05": 2178, "SM06": 2209, "SM10": 2420,
    "SM11": 2464, "SM12": 2534, "SM8": 2328, "SM9": 2377, "ST": 17674,
    "SVI": 22873, "SWSH01": 2585, "SWSH02": 2626, "SWSH03": 2675,
    "SWSH04": 2701, "SWSH05": 2765, "SWSH06": 2807, "SWSH07": 2848,
    "SWSH08": 2906, "SWSH09": 2948, "SWSH10": 3040, "SWSH11": 3118,
    "SWSH12": 3170,
}

with open('products/management/commands/sync_tcgcsv.py', encoding='utf-8') as f:
    content = f.read()

# Fix wrong group IDs
for abbrev, (old_id, new_id) in fixes.items():
    content = content.replace(f'"{abbrev}": {old_id}', f'"{abbrev}": {new_id}')

# Add missing sets - find the end of GROUP_CONFIG and insert before closing brace
insert_lines = '\n'.join(f'    "{abbrev}": {gid},' for abbrev, gid in missing.items())
content = content.replace(
    '"ME05": 24688,\n}',
    f'"ME05": 24688,\n{insert_lines}\n}}'
)

with open('products/management/commands/sync_tcgcsv.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Done! Fixed {len(fixes)} wrong IDs, added {len(missing)} missing sets")
