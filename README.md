# DSO Asset Tools

A pair of standalone Python scripts for working with **Drakensang Online**
game assets (DSOClient):

| Script | Purpose |
|---|---|
| `dso_bundle_extract.py` | Extracts `.nb` bundle files (`_B3N` format) into individual files |
| `nvx2_to_obj.py` | Converts `.nvx2` 3D models to Wavefront `.obj` format (Blender-ready) |

Both scripts use only the Python standard library (`struct`, `zlib`, `os`, `sys`) — no external dependencies required.

> **Requirements:** Python 3.7+
> **Note:** these tools were built from reverse-engineering the game's file format and are intended for personal use (backups, modding, research) — use them in accordance with the game's terms of service.

---

## 1. `dso_bundle_extract.py` — extracting bundles

### `_B3N` format overview

- Header: magic `_B3N` + `HB3N`, entry count, table offsets
- File name table
- Metadata table (MD5, size, data offset) — 44 bytes per entry
- Data block — each file additionally wrapped in `__ZN` + zlib compression

See the docstring at the top of the file for the full format breakdown.

### Usage

**Extract a single bundle:**

```bash
python dso_bundle_extract.py bundle63.nb extracted/
```

**Preview the bundle list from a TOC file** (index file, also `__ZN`-compressed):

```bash
python dso_bundle_extract.py --toc toc_file extracted_toc.txt
```

**Automatically extract ALL bundles in a folder** (e.g. the game cache) —
the script detects file type by content, not by file name:

```bash
python dso_bundle_extract.py --dir "C:\Users\<user>\AppData\Local\Temp\DSOClient\bundles" extracted/
```

### PowerShell version (Windows)

If you'd rather use an explicit PowerShell loop instead of `--dir`, for all `*.nb` files in a folder:

```powershell
Get-ChildItem -Path "C:\path\to\bundles" -Filter *.nb -File | ForEach-Object {
    python dso_bundle_extract.py $_.FullName "extracted"
}
```

---

## 2. `nvx2_to_obj.py` — converting NVX2 models to OBJ

### Supported variant

44-byte vertex (11 DWORDs):

- position `x, y, z` (float)
- normal (3× `int8`, normalized `/127`)
- UV coordinates (2× `uint16`, normalized `/8191`, V flipped for OBJ convention)
- remaining 6 DWORDs (tangent/binormal/other) — skipped on export

> Positions and triangles (i.e. the model's shape) are verified to be 100% correct. Normal/UV decoding was reconstructed from data analysis, so shading may differ slightly from the original.

### Usage — single file

```bash
python nvx2_to_obj.py model.nvx2 model.obj
```

### Batch conversion — PowerShell

**Option A — `.obj` files next to the originals (same name, different extension), recursing through subfolders:**

```powershell
Get-ChildItem -Path "C:\path\to\models" -Filter *.nvx2 -File -Recurse | ForEach-Object {
    $outPath = $_.FullName -replace '\.nvx2$', '.obj'
    python nvx2_to_obj.py $_.FullName $outPath
}
```

**Option B — all `.obj` files go into a single output folder:**

```powershell
$outDir = "C:\path\to\obj_output"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Get-ChildItem -Path "C:\path\to\models" -Filter *.nvx2 -File -Recurse | ForEach-Object {
    $outFile = Join-Path $outDir ($_.BaseName + ".obj")
    python nvx2_to_obj.py $_.FullName $outFile
}
```

**Option C — same as above, but preserving the subfolder structure in the output:**

```powershell
$inDir  = "C:\path\to\models"
$outDir = "C:\path\to\obj_output"

Get-ChildItem -Path $inDir -Filter *.nvx2 -File -Recurse | ForEach-Object {
    $relative = $_.FullName.Substring($inDir.Length).TrimStart('\')
    $outFile  = Join-Path $outDir ($relative -replace '\.nvx2$', '.obj')
    New-Item -ItemType Directory -Force -Path (Split-Path $outFile) | Out-Null
    python nvx2_to_obj.py $_.FullName $outFile
}
```

---

## Full workflow example

```powershell
# 1. Extract all bundles from the game cache
python dso_bundle_extract.py --dir "C:\Users\<user>\AppData\Local\Temp\DSOClient\bundles" extracted

# 2. Convert all extracted .nvx2 models to .obj (preserving folder structure)
$inDir  = "extracted"
$outDir = "extracted_obj"

Get-ChildItem -Path $inDir -Filter *.nvx2 -File -Recurse | ForEach-Object {
    $relative = $_.FullName.Substring((Resolve-Path $inDir).Path.Length).TrimStart('\')
    $outFile  = Join-Path $outDir ($relative -replace '\.nvx2$', '.obj')
    New-Item -ItemType Directory -Force -Path (Split-Path $outFile) | Out-Null
    python nvx2_to_obj.py $_.FullName $outFile
}
```

The resulting `.obj` files can be opened directly in Blender
(File → Import → Wavefront (.obj)).

---

## License

Scripts provided for personal / educational use. The game's file formats
are the property of their respective creators (Bigpoint / Bright Eyes) —
these tools do not contain any original game assets.
