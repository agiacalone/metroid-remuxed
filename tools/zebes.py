"""Read a Metroid ROM's world: the 32x32 room grid and the special-object
tables (doors, elevators, items), for drawing a seed's map."""
HEADER = 0x10
BANK = 0x4000
WORLD_MAP = 0x253E          # bank 0 $A53E: room number per cell, $FF = none
AREA_BANKS = {1: "Brinstar", 2: "Norfair", 3: "Tourian", 4: "Kraid", 5: "Ridley"}


def world(rom):
    return rom[HEADER + WORLD_MAP:HEADER + WORLD_MAP + 0x400]


def specials(rom):
    """Yield (bank, x, y, type, data) for every special-object table entry.
    Each area bank keeps a pointer to its table at $9598. The table is a list
    of rows: Y, pointer to the next row ($FFFF = last), then entries of
    X, offset to the next entry ($FF = last), and the objects."""
    for bank in AREA_BANKS:
        lo = HEADER + bank * BANK
        rd = lambda a: rom[lo + a - 0x8000]
        a = rd(0x9598) | rd(0x9599) << 8
        for _ in range(64):
            y = rd(a)
            nxt = rd(a + 1) | rd(a + 2) << 8
            e = a + 3
            for _ in range(32):
                x, off = rd(e), rd(e + 1)
                end = e + off if off != 0xFF else None
                p = e + 2
                yield bank, x, y, p, end, rd
                if off == 0xFF:
                    break
                e += off
            if nxt == 0xFFFF:
                break
            a = nxt


ENTRY_SIZES = {1: 3, 2: 2, 4: 2, 6: 1, 7: 3}


def area_reader(rom, bank):
    lo = HEADER + bank * BANK
    return lambda a: rom[lo + a - 0x8000]


def room_entries(rom, bank, room):
    """Entries after a room's objects: (type, bytes). Doors are type 2."""
    rd = area_reader(rom, bank)
    rpt = rd(0x959A) | rd(0x959B) << 8
    p = rd(rpt + 2 * room) | rd(rpt + 2 * room + 1) << 8
    i = p + 1
    while rd(i) not in (0xFD, 0xFF):
        i += 3
    out = []
    if rd(i) == 0xFF:
        return out
    i += 1
    while rd(i) != 0xFF:
        t = rd(i) & 0x0F
        n = ENTRY_SIZES[t]
        out.append((t, [rd(i + k) for k in range(n)]))
        i += n
    return out


def start_cell(rom, bank):
    rd = area_reader(rom, bank)
    return rd(0x95D7), rd(0x95D8)


AREA_BANK = {0: 1, 1: 2, 2: 4, 3: 3, 4: 5}     # elevator area id -> bank


def explore(rom, right_nibble=0xA):
    """Walk the world as the game scrolls it. Returns {(x, y): cell} with the
    area bank, orientation ('H' or 'V'), doors {'L','R'}, elevator flag and
    the set of neighbours it connects to."""
    w = world(rom)
    room = lambda x, y: w[y * 32 + x] if 0 <= x < 32 and 0 <= y < 32 else 0xFF
    elevators = {}
    hdoors = set()
    for bank, x, y, p, end, rd in specials(rom):
        t = rd(p) & 0x0F
        if t == 4:
            elevators[(bank, x, y)] = rd(p + 1)
        if t == 9:
            hdoors.add((bank, x, y))
    cells = {}

    def doors(bank, x, y):
        d = set()
        for t, b in room_entries(rom, bank, room(x, y)):
            if t == 2:
                d.add("R" if b[1] >> 4 == right_nibble else "L")
        return d

    # Grow every area from its start cell, breadth first, so each claims its
    # own rooms before a neighbour can. A start on an elevator is the bottom
    # of a shaft (vertical); the game start is a corridor (horizontal).
    from collections import deque
    todo = deque()
    late = []
    for bank in AREA_BANKS:
        sx, sy = start_cell(rom, bank)
        todo.append((bank, sx, sy, "V" if (bank, sx, sy) in elevators else "H"))
    # Then every cell with a special object (item, elevator, door marker),
    # whose table says which area it is in, so no such room is lost when a
    # branch is missed. Vertical if the grid has a room above or below.
    for bank, x, y, *_ in specials(rom):
        vert = room(x, y - 1) != 0xFF or room(x, y + 1) != 0xFF
        late.append((bank, x, y, "V" if vert else "H"))
    while todo or late:
        if not todo:
            todo.append(late.pop(0))
        bank, x, y, o = todo.popleft()
        if room(x, y) == 0xFF or (x, y) in cells:
            continue
        d = doors(bank, x, y)
        c = cells[(x, y)] = {"bank": bank, "o": o, "doors": d, "elev": (bank, x, y) in elevators, "links": set()}
        steps = [("L", -1, 0), ("R", 1, 0)] if o == "H" else [("U", 0, -1), ("D", 0, 1)]
        for side, dx, dy in steps:
            if room(x + dx, y + dy) == 0xFF:
                continue
            # An elevator ends its area's shaft: a down-elevator at the
            # bottom, an up-elevator (bit 7) at the top.
            e = elevators.get((bank, x, y))
            if e is not None and dy == (-1 if e & 0x80 else 1):
                continue
            if dx and (side in d or ("R" if side == "L" else "L") in doors(bank, x + dx, y)):
                continue
            c["links"].add(side)
            todo.append((bank, x + dx, y + dy, o))
        for side, dx in (("L", -1), ("R", 1)):
            other = "R" if side == "L" else "L"
            # A door can be recorded in either room. The neighbour's area is
            # this one's: only elevators change area.
            if room(x + dx, y) != 0xFF and (side in d or other in doors(bank, x + dx, y)):
                d.add(side)
                c["links"].add(side)
                keep = (bank, x, y) in hdoors and (bank, x + dx, y) in hdoors
                todo.append((bank, x + dx, y, o if keep else ("V" if o == "H" else "H")))
    return cells


# Metroid + Saving's map tiles: walls where a room does not scroll on, light
# notches where it has a door. Variants are (no door, left, right, both).
SHAFT_TOP, SHAFT_MID, SHAFT_BOT, SINGLE = (0x9A, 0x9B, 0x9C, 0x9D), (0x9E, 0x9F, 0xAA, 0xAB), (0xAC, 0xAD, 0xAE, 0xAF), (0xB5, 0xB6, 0xB7, 0xB8)
CORR_LEFT, CORR_MID, CORR_RIGHT = (0xB0, 0xB1), 0xB4, (0xB2, 0xB3)
EMPTY = 0xFE
ELEVATOR = 0xB9


def tile(cell):
    d = cell["doors"]
    scroll = cell["links"] - d
    v = ("L" in d) | ("R" in d) << 1
    if "U" in scroll or "D" in scroll:
        if "U" in scroll and "D" in scroll:
            return SHAFT_MID[v]
        return SHAFT_TOP[v] if "D" in scroll else SHAFT_BOT[v]
    if "L" in scroll and "R" in scroll:
        return CORR_MID
    if "R" in scroll:
        return CORR_LEFT["L" in d]
    if "L" in scroll:
        return CORR_RIGHT["R" in d]
    return SINGLE[v]


def prune_fillers(rom, cells):
    """Drop shaft dead ends with no doors and nothing in them. The grid puts a
    room past many shaft ends so the scroll engine has something to load;
    Samus cannot get there, and Metroid + Saving does not draw them."""
    special = {(x, y) for _b, x, y, *_ in specials(rom)}
    step = {"U": (0, -1), "D": (0, 1)}
    while True:
        drop = [xy for xy, c in cells.items()
                if c["o"] == "V" and not c["doors"] and xy not in special
                and len(c["links"]) == 1 and c["links"] <= {"U", "D"}]
        if not drop:
            return cells
        for (x, y) in drop:
            (side,) = cells[(x, y)]["links"]
            dx, dy = step[side]
            n = cells.get((x + dx, y + dy))
            if n:
                n["links"].discard("D" if side == "U" else "U")
            del cells[(x, y)]


def tilemap(rom):
    out = bytearray([EMPTY] * 0x400)
    for (x, y), cell in prune_fillers(rom, explore(rom)).items():
        out[y * 32 + x] = tile(cell)
    # Elevators: dotted shaft from a down-elevator to the cell where its
    # destination area starts, through cells that hold no drawn room.
    for bank, x, y, p, end, rd in specials(rom):
        if rd(p) & 0x0F != 4 or rd(p + 1) & 0x80:
            continue
        dest = AREA_BANK.get(rd(p + 1) & 0x0F)
        if dest is None:
            continue
        dx, dy = start_cell(rom, dest)
        if dx != x or dy <= y:
            continue
        for yy in range(y + 1, dy):
            if out[yy * 32 + x] == EMPTY:
                out[yy * 32 + x] = ELEVATOR
    return out
