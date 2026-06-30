# Vega Nesting

A web-based 2D nesting application that optimizes how sheet metal parts are arranged on plates to minimize waste. Upload DXF files, set your sheet dimensions and spacing, and get optimized layout results back as DXF — ready for your cutting machine.

## Why?

In sheet metal cutting, every percent of material saved directly impacts the bottom line. Manual part placement is slow and rarely optimal. Vega Nesting automates this:

- Drag and drop DXF files onto a web interface
- Configure sheet size and part spacing
- Let the engine compute the best arrangement in the background
- Download result DXF files for direct use on the cutting floor

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| Nesting engine | `lbf` (Rust, built on [jagua-rs](https://github.com/VovaStelmashchuk/jagua-rs)) |
| Geometry processing | Shapely + ezdxf |
| Database | SQLite |
| Frontend | Jinja2 templates + vanilla JS |
| Container | Docker (multi-stage build) |

## How It Works

1. User uploads DXF files → parsed with `ezdxf`, converted to closed polygons
2. Part geometries are buffered via `shapely` (spacing allowance)
3. Buffered shapes are sent as JSON to the `lbf` Rust engine → optimal placement computed
4. Result coordinates map each part back onto the DXF sheet
5. User downloads the output DXF files

## Installation

### Requirements

- Python 3.11+
- Rust (only needed to compile the `lbf` engine — Docker handles this automatically)

### Local Setup

```bash
git clone https://github.com/sngzege/vega-nesting.git
cd vega-nesting/server

pip install -r app/requirements.txt

# Build the lbf engine (Linux)
cd app
bash build_engine.sh
chmod +x lbf
cd ..

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.



## Usage

1. **Log in** — enter a username (stored in SQLite, no password needed)
2. **Create a project** — set plate width, height, and spacing
3. **Upload DXF** — drag and drop part files, specify quantities
4. **Run** — nesting runs as a background job
5. **Download** — grab the result DXF files

Projects are persisted and can be reopened later.

## Project Structure

```
vega-nesting/
├── server/
│   ├── app/
│   │   ├── main.py              # FastAPI app and endpoints
│   │   ├── database.py          # SQLite database layer
│   │   ├── build_engine.sh      # Script to compile the lbf engine
│   │   ├── requirements.txt     # Python dependencies
│   │   ├── nesting/
│   │   │   ├── engine.py        # Nesting workflow orchestrator
│   │   │   ├── build_geometry.py# DXF → Shapely geometry conversion
│   │   │   ├── dxf_utils.py     # DXF reading/cleaning helpers
│   │   │   ├── dxf_parser.py    # DXF file parser
│   │   │   ├── input_builder.py # JSON input builder for lbf engine
│   │   │   └── svg_generator.py # SVG preview generator
│   │   ├── templates/           # Jinja2 HTML templates
│   │   ├── static/              # CSS, JS assets
│   │   ├── uploads/             # Uploaded DXF files
│   │   └── output/              # Computed result files
│   ├── tests/                   # pytest test suite
│   ├── Dockerfile               # Multi-stage Docker build
│   └── docker-compose.yml       # Docker Compose config
└── README.md
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/api/login` | POST | User login |
| `/api/projects` | POST | Create a new project |
| `/api/projects/{id}` | GET | Project details |
| `/api/projects/{id}/files` | POST | Upload DXF files |
| `/api/projects/{id}/nest` | POST | Start nesting computation |
| `/api/jobs/{id}` | GET | Poll job status |

Swagger docs available at `http://localhost:8000/docs`.

## Testing

```bash
cd server/tests
pytest -v
```

On Windows, the `lbf` binary is not required — tests use mocks for the engine.

## License

Not yet specified.
