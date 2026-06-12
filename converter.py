#!/usr/bin/env python3
"""
bms-converter: Watches bms_kb for new files and converts them to markdown in bms_kb_md.
"""

import os
import sys
import time
import logging
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("bms-converter")

WATCH_DIR  = Path(os.environ.get("WATCH_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/output"))

CODE_EXTS = {".py", ".js", ".aut", ".tgml", ".xml"}
SKIP_EXTS = {".xbk", ".bak", ".tmp", ".log"}
SKIP_DIRS = {"OLD", "old", "archive", "8_BACKUPS", "Temp", "temp"}


def output_path(input_path: Path) -> Path:
    rel = input_path.relative_to(WATCH_DIR)
    return OUTPUT_DIR / rel.with_suffix(".md")


def already_converted(input_path: Path) -> bool:
    out = output_path(input_path)
    if not out.exists():
        return False
    return out.stat().st_mtime >= input_path.stat().st_mtime


def convert_pdf(path: Path) -> str:
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
        converter = PdfConverter(artifact_dict=create_model_dict())
        rendered = converter(str(path))
        text, _, _ = text_from_rendered(rendered)
        return text
    except Exception as e:
        log.error(f"PDF conversion failed for {path.name}: {e}")
        return f"# {path.stem}\n\n*Conversion failed: {e}*\n"


def convert_xlsx(path: Path) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        md = f"# {path.stem}\n\n"
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            md += f"## {sheet_name}\n\n"
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            # Header row
            header = [str(c) if c is not None else "" for c in rows[0]]
            md += "| " + " | ".join(header) + " |\n"
            md += "| " + " | ".join(["---"] * len(header)) + " |\n"
            for row in rows[1:]:
                cells = [str(c) if c is not None else "" for c in row]
                md += "| " + " | ".join(cells) + " |\n"
            md += "\n"
        return md
    except Exception as e:
        log.error(f"XLSX conversion failed for {path.name}: {e}")
        return f"# {path.stem}\n\n*Conversion failed: {e}*\n"


def convert_xls(path: Path) -> str:
    try:
        import xlrd
        wb = xlrd.open_workbook(path)
        md = f"# {path.stem}\n\n"
        for sheet in wb.sheets():
            md += f"## {sheet.name}\n\n"
            if sheet.nrows == 0:
                continue
            header = [str(sheet.cell_value(0, c)) for c in range(sheet.ncols)]
            md += "| " + " | ".join(header) + " |\n"
            md += "| " + " | ".join(["---"] * len(header)) + " |\n"
            for r in range(1, sheet.nrows):
                row = [str(sheet.cell_value(r, c)) for c in range(sheet.ncols)]
                md += "| " + " | ".join(row) + " |\n"
            md += "\n"
        return md
    except Exception as e:
        log.error(f"XLS conversion failed for {path.name}: {e}")
        return f"# {path.stem}\n\n*Conversion failed: {e}*\n"


def convert_csv(path: Path) -> str:
    try:
        import pandas as pd
        df = pd.read_csv(path, dtype=str).fillna("")
        md = f"# {path.stem}\n\n"
        md += df.to_markdown(index=False)
        md += "\n"
        return md
    except Exception as e:
        log.error(f"CSV conversion failed for {path.name}: {e}")
        return f"# {path.stem}\n\n*Conversion failed: {e}*\n"


def convert_code(path: Path) -> str:
    ext_map = {".py": "python", ".js": "javascript", ".aut": "text", ".tgml": "xml", ".xml": "xml"}
    lang = ext_map.get(path.suffix.lower(), "text")
    try:
        content = path.read_text(errors="replace")
        return f"# {path.stem}\n\n```{lang}\n{content}\n```\n"
    except Exception as e:
        return f"# {path.stem}\n\n*Read failed: {e}*\n"


def convert_file(path: Path) -> bool:
    ext = path.suffix.lower()

    if ext in SKIP_EXTS:
        return False

    for skip in SKIP_DIRS:
        if skip in path.parts:
            return False

    if already_converted(path):
        log.info(f"  ⏭  Already converted, skipping: {path.name}")
        return False

    log.info(f"🔄 Converting: {path.relative_to(WATCH_DIR)}")

    if ext == ".pdf":
        content = convert_pdf(path)
    elif ext in {".xlsx", ".xlsm"}:
        content = convert_xlsx(path)
    elif ext in {".xls"}:
        content = convert_xls(path)
    elif ext == ".csv":
        content = convert_csv(path)
    elif ext in CODE_EXTS:
        content = convert_code(path)
    elif ext == ".md":
        content = path.read_text(errors="replace")
    else:
        log.debug(f"  ⏭  Unsupported extension: {ext}")
        return False

    out = output_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    log.info(f"  ✅ Saved: {out.relative_to(OUTPUT_DIR)}")
    return True


class ConvertHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        time.sleep(2)
        convert_file(Path(event.src_path))

    def on_modified(self, event):
        if event.is_directory:
            return
        convert_file(Path(event.src_path))

    def on_moved(self, event):
        if event.is_directory:
            return
        convert_file(Path(event.dest_path))


def startup_scan():
    all_files = [p for p in WATCH_DIR.rglob("*") if p.is_file()]
    log.info(f"🔍 Startup scan: found {len(all_files)} file(s)...")
    success = 0
    for path in sorted(all_files):
        if convert_file(path):
            success += 1
    log.info(f"✅ Startup scan complete: {success} file(s) converted.")


def main():
    if not WATCH_DIR.exists():
        log.error(f"Input directory does not exist: {WATCH_DIR}")
        sys.exit(1)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("bms-converter starting")
    log.info(f"  Input:   {WATCH_DIR}")
    log.info(f"  Output:  {OUTPUT_DIR}")
    log.info("=" * 60)

    startup_scan()

    handler = ConvertHandler()
    observer = Observer()
    observer.schedule(handler, str(WATCH_DIR), recursive=True)
    observer.start()
    log.info(f"👁  Watching {WATCH_DIR} for changes...")

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
