#!/usr/bin/env python3
"""
Debooklet a scanned PDF booklet using pypdf.

Input PDF pages (must be even count) follow this arrangement (N = 2 * input_pages):
  page 1:  N | 1
  page 2:  2 | N-1
  page 3:  N-2 | 3
  page 4:  4 | N-3
  ...
  last:    N/2 | N/2+1

Each input page is split vertically into left/right halves, scaled to A4,
written as zero-padded numbered PDFs into ./temp, then merged in numerical order.
"""

import argparse
import math
import shutil
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from pypdf.generic import RectangleObject

# A4 size in points (1 pt = 1/72 inch)
A4_WIDTH = 595.2756
A4_HEIGHT = 841.8898

# project root
ROOT = Path.cwd()


def ensure_temp_dir(temp_dir: Path) -> None:
    """Remove temp_dir if it exists, then create it fresh."""
    if temp_dir.exists():
        if not temp_dir.is_dir():
            raise RuntimeError(f"{temp_dir} exists but is not a directory")
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)


def remove_temp_dir(temp_dir: Path) -> None:
    """Remove the temporary directory and its contents."""
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def pad_width(total_pages: int) -> int:
    """Return the number of digits needed for zero-padding (e.g. 3 for 100 pages)."""
    return max(1, math.ceil(math.log10(total_pages + 1)))


def make_padded_name(page_num: int, width: int) -> str:
    return f"{page_num:0{width}d}.pdf"


def crop_half(page: PageObject, side: str) -> PageObject:
    """
    Extract the left or right half of a page.
    The returned page always has mediabox origin at (0, 0).
    """
    mb = page.mediabox
    left = float(mb.left)
    bottom = float(mb.bottom)
    right = float(mb.right)
    top = float(mb.top)
    mid = (left + right) / 2.0
    half_w = (right - left) / 2.0
    h = top - bottom

    # Carrier that holds the original content
    carrier = PageObject.create_blank_page(width=right - left, height=h)
    carrier.merge_page(page)

    if side == "left":
        carrier.cropbox = RectangleObject((left, bottom, mid, top))
        carrier.mediabox = RectangleObject((left, bottom, mid, top))
        shift_x = -left          # normally 0
    else:
        carrier.cropbox = RectangleObject((mid, bottom, right, top))
        carrier.mediabox = RectangleObject((mid, bottom, right, top))
        shift_x = -mid

    # Clean half-page with origin (0, 0)
    half = PageObject.create_blank_page(width=half_w, height=h)
    transform = Transformation().translate(tx=shift_x, ty=-bottom)
    half.merge_transformed_page(carrier, transform)

    half.mediabox = RectangleObject((0, 0, half_w, h))
    half.cropbox = RectangleObject((0, 0, half_w, h))
    return half


def scale_to_a4(page: PageObject) -> PageObject:
    """
    Create a new A4 page and place the given page content scaled to fit A4
    (preserving aspect ratio, centred).
    """
    src_w = float(page.mediabox.width)
    src_h = float(page.mediabox.height)

    if src_w <= 0 or src_h <= 0:
        raise ValueError("Page has zero or negative dimensions")

    scale = min(A4_WIDTH / src_w, A4_HEIGHT / src_h)
    scaled_w = src_w * scale
    scaled_h = src_h * scale
    offset_x = (A4_WIDTH - scaled_w) / 2
    offset_y = (A4_HEIGHT - scaled_h) / 2

    a4_page = PageObject.create_blank_page(width=A4_WIDTH, height=A4_HEIGHT)
    transform = (
        Transformation()
        .scale(sx=scale, sy=scale)
        .translate(tx=offset_x, ty=offset_y)
    )
    a4_page.merge_transformed_page(page, transform)
    return a4_page


def write_single_page_pdf(page: PageObject, path: Path) -> None:
    writer = PdfWriter()
    writer.add_page(page)
    with open(path, "wb") as f:
        writer.write(f)


def logical_page_numbers(input_index: int, total_logical: int) -> tuple[int, int]:
    """
    Given 0-based input page index and total logical pages N,
    return (left_logical, right_logical) 1-based page numbers.
    """
    k = input_index // 2
    if input_index % 2 == 0:
        left = total_logical - 2 * k
        right = 1 + 2 * k
    else:
        left = 2 + 2 * k
        right = total_logical - 1 - 2 * k
    return left, right


def debooklet(input_path: Path, output_path: Path, temp_dir: Path = Path("./temp"), do_scale_to_a4: bool = False) -> None:
    if input_path.suffix != ".pdf":
        raise Exception(f"File {str(input_path)} does not end with .pdf")

    reader = PdfReader(str(input_path))
    num_input = len(reader.pages)

    if num_input == 0:
        raise ValueError("Input PDF has no pages")
    if num_input % 2 != 0:
        raise ValueError(
            f"Number of pages in the input PDF must be even (got {num_input})"
        )

    total_logical = 2 * num_input
    width = pad_width(total_logical)

    print(f"Input pages : {num_input}")
    print(f"Logical pages: {total_logical}")
    print(f"Zero-pad width: {width}")

    ensure_temp_dir(temp_dir)

    try:
        for i in range(num_input):
            page = reader.pages[i]
            left_num, right_num = logical_page_numbers(i, total_logical)

            left_half = crop_half(page, "left")
            right_half = crop_half(page, "right")

            if do_scale_to_a4:
                left_half = scale_to_a4(left_half)
                right_half = scale_to_a4(right_half)

            left_path = temp_dir / make_padded_name(left_num, width)
            right_path = temp_dir / make_padded_name(right_num, width)

            write_single_page_pdf(left_half, left_path)
            write_single_page_pdf(right_half, right_path)

            print(f"  input[{i+1}] → {left_path.name}  &  {right_path.name}")

        # Merge in numerical order
        print("Merging...")
        merger = PdfWriter()
        for p in range(1, total_logical + 1):
            pdf_path = temp_dir / make_padded_name(p, width)
            if not pdf_path.exists():
                raise FileNotFoundError(f"Expected temporary file missing: {pdf_path}")
            part = PdfReader(str(pdf_path))
            merger.add_page(part.pages[0])

        with open(output_path, "wb") as f:
            merger.write(f)

        print(f"Wrote {output_path} ({total_logical} pages)")

    finally:
        remove_temp_dir(temp_dir)
        print("Cleaned up temporary directory")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debooklet a scanned PDF (split spreads, reorder to sequential A4 pages)"
    )
    parser.add_argument("input", type=Path, help="Input booklet PDF or path")
    parser.add_argument("--scale-to-a4", action="store_true", help="Scale each debookleted page to A4")
    parser.add_argument(
        "--temp-dir",
        type=Path,
        default=Path("./temp"),
        help="Temporary directory for intermediate single-page PDFs (default: ./temp)",
    )
    args = parser.parse_args()

    if not args.input.is_file() and not args.input.is_dir():
        print(f"Error: input file or path not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    input_type = "file" if args.input.is_file() else "directory"
    print(f"Debookleting on {input_type} {args.input}...")

    output_dir = ROOT / "output"

    if output_dir.exists():
        _ans = input("[WARNING] output folder exists, all of its contents will be REMOVED! Do you wish to continue? [y/N]: ")
        if _ans.lower().strip() != "y":
            print("Aborting...")
            sys.exit(0)
        shutil.rmtree(output_dir)

    output_dir.mkdir(exist_ok=True)

    try:
        if input_type == "file":
            input_stem = Path(args.input).stem
            output = output_dir / f"{input_stem}_debookleted.pdf"
            debooklet(args.input, output, args.temp_dir, args.scale_to_a4)
        else:
            original_pdf_files = [f for f in args.input.glob("*.pdf") if f.is_file()]
            if not original_pdf_files:
                print(f"[WARNING] No pdf files found in directory {args.input}.")
                sys.exit(0)

            skipped = 0

            for i in range(len(original_pdf_files)):
                file = original_pdf_files[i]
                print(f"Processing [{i+1}/{len(original_pdf_files)}]: {str(file)}")
                try:
                    input_stem = Path(file).stem
                    output = output_dir / f"{input_stem}_debookleted.pdf"
                    debooklet(file, output, args.temp_dir, args.scale_to_a4)
                except Exception as e:
                    print(f"Error occurred while proccessing {str(file)}. Skipping...")
                    print(e)
                    skipped += 1

            print()
            print("===== Summary =====")
            print(f"Debookleted: {len(original_pdf_files) - skipped}")
            print(f"Skipped: {skipped}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
