# Design QA — Figma vs Web Screenshot Comparator

Compare Figma design screenshots against live webpage screenshots using Gemini Vision API. Returns a structured diff table with pixel-level estimates.

## How It Works

```
Figma PNG + Web PNG
        │
        ▼
  Pass 1: Element Inventory
  (discovers all UI elements in both images)
        │
        ▼
  Pass 2: Detailed Comparison
  (compares 8 property categories per element)
        │
        ▼
  Pass 3: Validation (optional)
  (re-checks low-confidence and dense-region items)
        │
        ▼
  Structured JSON diff table
```

### Difference Categories

| Type | What it checks |
|------|---------------|
| `text` | font-family, font-size, font-weight, content, line-height |
| `spacing` | margins, gaps between elements |
| `padding` | internal padding (top, right, bottom, left) |
| `color` | background, border, text color, opacity |
| `button` | CTA icon, text, background, border-radius, state |
| `component` | type mismatch, state, alignment, variant |
| `size` | width, height, border-radius |
| `missing` | element exists in one screenshot but not the other |

## Setup

```bash
# Clone and enter
cd design-qa

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

Get your Gemini API key from https://aistudio.google.com/apikey

## Run

```bash
# Start the server
uvicorn app.main:app --reload --port 8000

# Open docs
# http://localhost:8000/docs
```

## Usage

### cURL

```bash
curl -X POST http://localhost:8000/compare \
  -F "figma=@figma_screenshot.png" \
  -F "web=@web_screenshot.png" | jq .
```

### Python

```bash
python tests/test_compare.py figma_screenshot.png web_screenshot.png
```

### Shell script

```bash
chmod +x test_api.sh
./test_api.sh figma_screenshot.png web_screenshot.png
```

### Skip validation pass (faster, less accurate)

```bash
curl -X POST "http://localhost:8000/compare?skip_validation=true" \
  -F "figma=@figma.png" \
  -F "web=@web.png"
```

## Response Format

```json
{
  "total_diffs": 15,
  "by_severity": { "critical": 2, "major": 8, "minor": 5 },
  "by_type": { "text": 4, "spacing": 3, "size": 3, "component": 2, "missing": 2, "color": 1 },
  "diffs": [
    {
      "element": "Action Column",
      "text": "Actions",
      "diff_type": "size",
      "sub_type": "width",
      "figma_value": "72px",
      "web_value": "120px",
      "delta": "+48px",
      "severity": "major",
      "confidence": 0.88,
      "region": "table_header"
    }
  ],
  "summary": "15 differences found. Key issues: ..."
}
```

## Project Structure

```
design-qa/
├── app/
│   ├── main.py           # FastAPI app + /compare endpoint
│   ├── pipeline.py        # 3-pass comparison orchestrator
│   ├── gemini_client.py   # Gemini Vision API wrapper
│   ├── schemas.py         # Pydantic models (types + validation)
│   ├── image_utils.py     # PIL preprocessing (resize, normalize)
│   ├── config.py          # Settings from .env
│   └── prompts/
│       ├── inventory.py   # Pass 1: element discovery
│       ├── compare.py     # Pass 2: property comparison
│       └── validate.py    # Pass 3: re-check uncertain items
├── tests/
│   └── test_compare.py    # Python test client
├── test_api.sh            # Shell test script
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `GEMINI_API_KEY` | (required) | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash-preview-05-20` | Model to use |
| `GEMINI_TEMPERATURE` | `0.1` | Low = more deterministic |
| `MAX_IMAGE_DIM` | `2048` | Max px on longest side |

### Model Selection

- **`gemini-2.5-flash-preview-05-20`** — Fast, good for most pages. Use this for iteration.
- **`gemini-2.5-pro-preview-05-06`** — Slower but more accurate for complex UIs with many elements.

## Tips for Best Results

1. **Take screenshots at the same viewport width** (ideally 1440px). Mismatched widths create false positives.
2. **Capture the same state** — same scroll position, same filters applied, same data visible.
3. **Use PNG over JPG** — JPEG compression artifacts confuse the LLM.
4. **For complex pages**, run with `skip_validation=false` (default) to get the validation pass.
5. **The API docs at `/docs`** let you test directly in the browser with Swagger UI.
