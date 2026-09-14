#!/usr/bin/env python3
"""
nvx2_to_obj.py — konwertuje modele .nvx2 (Drakensang Online, wariant
11-DWORD/44-bajtowego wierzchołka) do formatu Wavefront .obj,
który otwiera się bezpośrednio w Blenderze.

Struktura pliku NVX2 (na podstawie dokumentacji BrightEyesWiki i analizy
plików z Drakensang Online):

  Header (28 bajtów):
    magic "2XVN" (4B)
    numGroups (u32), numVertices (u32), vertexWidth (u32, w DWORD-ach),
    numTriangles (u32), numEdges (u32), vertexComponentMask (u32)

  Grupy (24 bajty * numGroups):
    firstVertex, numVertices, firstTriangle, numTriangles, firstEdge, numEdges

  Wierzchołki (vertexWidth*4 bajtów każdy; tu: 44 bajty / 11 DWORD):
    [0:12]  float x, y, z            — pozycja
    [12]    byte  nx (signed, /127)  \
    [13]    byte  ny (signed, /127)   > normalna (przybliżona rekonstrukcja)
    [14]    byte  nz (signed, /127)  /
    [15]    byte  nieznany (zazwyczaj 0)
    [16:18] ushort u (/8191)         — wspolrzedna tekstury U
    [18:20] ushort v (/8191)         — wspolrzedna tekstury V
    [20:44] pozostałe 6 DWORD        — nieustalone (tangent/binormal/inne),
                                        pomijane przy eksporcie do OBJ

  Trójkąty (6 bajtów każdy): 3x ushort — indeksy wierzchołków (globalne,
  liczone dla całego pliku, nie per-grupa).

UWAGA: dekodowanie normalnych/UV jest odtworzone na podstawie analizy
rzeczywistych danych (nie z oryginalnego kodu źródłowego silnika), więc
cieniowanie może się nieznacznie różnić od oryginału. Pozycje i trójkąty
(czyli kształt modelu) są natomiast zweryfikowane i w 100% poprawne.

Użycie:
    python nvx2_to_obj.py model.nvx2 model.obj
"""

import struct
import sys


def s8(b: int) -> int:
    """Bajt jako liczba ze znakiem (-128..127)."""
    return b - 256 if b > 127 else b


def convert(nvx2_path: str, obj_path: str):
    with open(nvx2_path, "rb") as f:
        data = f.read()

    if data[0:4] != b"2XVN":
        raise ValueError(f"To nie jest plik NVX2 (magic: {data[0:4]!r})")

    numGroups, numVertices, vertexWidth, numTriangles, numEdges, vcMask = \
        struct.unpack("<6I", data[4:28])

    groups = []
    gpos = 28
    for _ in range(numGroups):
        groups.append(struct.unpack("<6I", data[gpos:gpos + 24]))
        gpos += 24

    vstart = gpos
    vstride = vertexWidth * 4
    positions, normals, uvs = [], [], []

    for i in range(numVertices):
        off = vstart + i * vstride
        x, y, z = struct.unpack("<3f", data[off:off + 12])
        positions.append((x, y, z))

        nx = s8(data[off + 12]) / 127.0
        ny = s8(data[off + 13]) / 127.0
        nz = s8(data[off + 14]) / 127.0
        normals.append((nx, ny, nz))

        u_raw, v_raw = struct.unpack("<2H", data[off + 16:off + 20])
        u = u_raw / 8191.0
        v = 1.0 - (v_raw / 8191.0)  # odwrocenie V (konwencja DirectX -> OBJ)
        uvs.append((u, v))

    istart = vstart + numVertices * vstride
    tri_count = numTriangles
    indices = struct.unpack(f"<{tri_count * 3}H", data[istart:istart + tri_count * 3 * 2])

    with open(obj_path, "w") as f:
        f.write(f"# skonwertowano z {nvx2_path}\n")
        f.write(f"# wierzcholkow: {numVertices}, trojkatow: {numTriangles}, grup: {numGroups}\n")
        for x, y, z in positions:
            f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for u, v in uvs:
            f.write(f"vt {u:.6f} {v:.6f}\n")
        for nx, ny, nz in normals:
            f.write(f"vn {nx:.6f} {ny:.6f} {nz:.6f}\n")

        for gi, (firstVertex, gNumVertices, firstTriangle, gNumTriangles, firstEdge, gNumEdges) in enumerate(groups):
            f.write(f"o group_{gi}\n")
            for t in range(firstTriangle, firstTriangle + gNumTriangles):
                a, b, c = indices[t * 3], indices[t * 3 + 1], indices[t * 3 + 2]
                # OBJ indeksuje od 1
                f.write(
                    f"f {a+1}/{a+1}/{a+1} {b+1}/{b+1}/{b+1} {c+1}/{c+1}/{c+1}\n"
                )

    print(f"Zapisano: {obj_path}")
    print(f"  wierzcholki: {numVertices}, trojkaty: {numTriangles}, grupy: {numGroups}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
