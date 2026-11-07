# debooklet.py

Debooklet a scanned PDF booklet or a directory of them using [pypdf](https://pypdf.readthedocs.io/).

Takes a PDF that was scanned as a booklet (two logical pages side-by-side on each physical page) and produces a normal sequential A4 PDF with one logical page per page.

**Supports both single-file and mass (directory) processing.** Drop a whole folder of booklet PDFs and it will debooklet every `.pdf` inside it automatically.

## How the input is arranged

For a booklet with **N** logical pages (N must be even, and the input PDF must contain exactly **N/2** pages):

| Input page | Left half | Right half |
|------------|-----------|------------|
| 1          | N         | 1          |
| 2          | 2         | N-1        |
| 3          | N-2       | 3          |
| 4          | 4         | N-3        |
| ...        | ...       | ...        |
| last       | N/2       | N/2 + 1    |

Each input page is split vertically into left/right halves, optionally scaled to fit A4 (preserving aspect ratio, centred), written as temporary single-page PDFs, then merged in numerical order.

## Requirements

- Python 3.8+
- [`pypdf`](https://pypdf.readthedocs.io/)

```
pip install pypdf
```

## Usage

### Mass debooklet (directory)

Point the script at a folder and it will process **every** `.pdf` inside it:

```
python debooklet.py /path/to/folder/
```

- Each successful file is written to `./output/<stem>_debookleted.pdf`
- Failed files are skipped and reported in a summary at the end
- Ideal for batch-processing many scanned booklets at once

### Single file

```
python debooklet.py input.pdf
```

Output is written to:

```
./output/<input_stem>_debookleted.pdf
```

### Options

| Argument     | Description                                      | Default   |
|--------------|--------------------------------------------------|-----------|
| `input`      | Input PDF file **or** directory containing PDFs  | required  |
| `--temp-dir` | Directory used for intermediate single-page PDFs | `./temp`  |

The temporary directory is created fresh for each run and deleted when finished.

## Example (directory / mass mode)

```
python debooklet.py ./scanned_booklets/
```

Console output roughly looks like:

```
Debookleting on directory ./scanned_booklets/...
Processing [1/3]: scanned_booklets/booklet_a.pdf
Input pages : 8
Logical pages: 16
  ...
Wrote output/booklet_a_debookleted.pdf (16 pages)
Processing [2/3]: scanned_booklets/booklet_b.pdf
  ...
Processing [3/3]: scanned_booklets/booklet_c.pdf
  ...

===== Summary =====
Debookleted: 3
Skipped: 0
```

## Notes

- Input page count **must be even**.
- Each half-page is optionally scaled to fit A4 while preserving aspect ratio and centred on the page.
- The script is safe to run repeatedly; it always starts with a clean `temp` directory and removes it afterwards.
- Output directory `./output` is created automatically if it does not exist, and its contents are removed if it exists.
- Designed for convenient **batch / mass debookleting** of many PDFs in one go.
