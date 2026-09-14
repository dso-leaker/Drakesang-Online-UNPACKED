#!/usr/bin/env python3
"""
dso_bundle_extract.py — rozpakowuje pliki bundli (*.nb, format "_B3N")
z gry Drakensang Online (klient DSOClient).

Struktura pliku bundla:
  offset 0   : magic "_B3N" (4 bajty)
  offset 4   : magic "HB3N" (4 bajty)
  offset 8   : uint32 LE  num_entries   — liczba plików w bundlu
  offset 12  : uint32 LE  header_size   — offset początku tabeli nazw (=24)
  offset 16  : uint32 LE  names_end     — offset końca tabeli nazw / początku metadanych
  offset 20  : uint32 LE  meta_end      — offset końca metadanych / początku bloku danych

  Tabela nazw (od header_size do names_end):
      num_entries razy: uint16 LE dlugosc + surowy string (bez terminatora)

  Tabela metadanych (od names_end do meta_end), 44 bajty na wpis:
      [0:4]   uint32 LE  offset nazwy w tabeli nazw (informacyjne)
      [4:36]  32 bajty ASCII — MD5 (hex) zawartości pliku
      [36:40] uint32 LE  rozmiar danych pliku (skompresowanych, w bloku DATA)
      [40:44] uint32 LE  offset danych pliku (względem początku bloku DATA)

  Blok DATA (od meta_end do końca pliku):
      surowe dane wszystkich plików, jeden po drugim.
      KAŻDY plik wewnątrz jest dodatkowo owinięty w:
          "__ZN" (4B) + uint32 LE rozmiar_po_dekompresji (4B) + strumień zlib

Użycie:
    python dso_bundle_extract.py bundle63.nb wypakowane/
    python dso_bundle_extract.py --toc plik_toc wypakowane_toc.txt   (podgląd listy bundli)
"""

import struct
import zlib
import os
import sys


def unwrap_zn(chunk: bytes) -> bytes:
    """Zdejmuje wrapper __ZN + zlib, jeśli obecny."""
    if chunk[:4] == b"__ZN":
        usize = struct.unpack("<I", chunk[4:8])[0]
        raw = zlib.decompress(chunk[8:])
        if len(raw) != usize:
            print(f"  UWAGA: rozmiar po dekompresji ({len(raw)}) "
                  f"nie zgadza się z deklarowanym ({usize})")
        return raw
    return chunk


def extract_bundle(bundle_path: str, output_dir: str):
    with open(bundle_path, "rb") as f:
        data = f.read()

    if data[0:4] != b"_B3N" or data[4:8] != b"HB3N":
        raise ValueError(f"To nie wygląda na plik bundla _B3N (nagłówek: {data[0:8]!r})")

    num_entries, header_size, names_end, meta_end = struct.unpack("<4I", data[8:24])

    # 1. tabela nazw
    pos = header_size
    names = []
    for _ in range(num_entries):
        strlen = struct.unpack("<H", data[pos:pos + 2])[0]
        names.append(data[pos + 2:pos + 2 + strlen].decode("latin-1"))
        pos += 2 + strlen
    if pos != names_end:
        print(f"UWAGA: koniec tabeli nazw ({pos}) != names_end ({names_end}) "
              f"— format może się różnić w tej wersji gry.")

    # 2. tabela metadanych
    rec_size = 44
    records = []
    for i in range(num_entries):
        off = names_end + i * rec_size
        rec = data[off:off + rec_size]
        size, data_offset = struct.unpack("<2I", rec[36:44])
        md5hex = rec[4:36].decode("ascii", errors="replace")
        records.append((names[i], size, data_offset, md5hex))

    data_start = meta_end
    os.makedirs(output_dir, exist_ok=True)

    ok, fail = 0, 0
    for name, size, data_offset, md5hex in records:
        chunk = data[data_start + data_offset: data_start + data_offset + size]
        out_path = os.path.join(output_dir, name.replace("\\", "/"))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        try:
            raw = unwrap_zn(chunk)
            with open(out_path, "wb") as out_f:
                out_f.write(raw)
            ok += 1
        except Exception as e:
            fail += 1
            print(f"  BŁĄD przy '{name}': {e}")

    print(f"\nGotowe: {ok}/{num_entries} plików wypakowanych do '{output_dir}' "
          f"({fail} błędów).")


def extract_toc(toc_path: str, output_txt: str):
    with open(toc_path, "rb") as f:
        data = f.read()
    raw = unwrap_zn(data)
    with open(output_txt, "wb") as f:
        f.write(raw)
    lines = raw.decode("utf-8", errors="replace").splitlines()
    print(f"Zapisano listę {len(lines)} bundli do '{output_txt}'.")


def extract_folder(input_dir: str, output_dir: str):
    """
    Przechodzi po WSZYSTKICH plikach w folderze (np. Temp\\DSOClient\\bundles),
    rozpoznaje typ pliku po pierwszych bajtach (nie po nazwie!) i:
      - pliki bundli (_B3N)  -> rozpakowuje do output_dir
      - pliki toc (__ZN, zawierające tekst z "bundles/")  -> zapisuje jako .txt obok
      - inne pliki -> pomija
    """
    entries = sorted(os.listdir(input_dir))
    total_bundles = 0
    for entry in entries:
        full_path = os.path.join(input_dir, entry)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path, "rb") as f:
                head = f.read(8)
        except Exception:
            continue

        if head[0:4] == b"_B3N":
            print(f"\n=== Bundle: {entry} ===")
            try:
                extract_bundle(full_path, output_dir)
                total_bundles += 1
            except Exception as e:
                print(f"  BŁĄD: {e}")
        elif head[0:4] == b"__ZN":
            # to moze byc TOC albo pojedynczy skompresowany plik - sprobujmy jako TOC
            try:
                with open(full_path, "rb") as f:
                    data = f.read()
                raw = unwrap_zn(data)
                if b"bundles/" in raw[:200]:
                    out_txt = os.path.join(output_dir, "_toc_" + entry + ".txt")
                    os.makedirs(output_dir, exist_ok=True)
                    with open(out_txt, "wb") as out_f:
                        out_f.write(raw)
                    print(f"TOC zapisany: {entry} -> {out_txt}")
            except Exception:
                pass
        # inne pliki (np. dlcache) pomijamy po cichu

    print(f"\n=== Gotowe: rozpakowano {total_bundles} bundli do '{output_dir}' ===")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--toc":
        extract_toc(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == "--dir":
        extract_folder(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3:
        extract_bundle(sys.argv[1], sys.argv[2])
    else:
        print(__doc__)
        print("\nDodatkowo:")
        print("  python dso_bundle_extract.py --dir folder_z_bundlami folder_wyjsciowy")
        print("      (automatycznie wykrywa i rozpakowuje WSZYSTKIE bundle w folderze)")
        sys.exit(1)
