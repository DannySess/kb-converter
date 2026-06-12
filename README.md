# bms-converter

Watches a folder for BMS documents and converts them to Markdown for ingestion into Open WebUI.

## Supported formats

| Format | Method |
|---|---|
| PDF | marker-pdf |
| XLSX/XLSM | openpyxl |
| XLS | xlrd |
| CSV | pandas |
| PY/JS/AUT/TGML | code block |
| MD | copy as-is |

## Usage

```bash
docker build -t bms-converter:latest .
docker-compose up -d
docker logs -f bms-converter
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| WATCH_DIR | /input | Source folder (mounted from NAS bms_kb) |
| OUTPUT_DIR | /output | Output folder (mounted from NAS bms_kb_md) |
