# Vega Nesting

2D sac metal parçalarını sheet (plaka) üzerine en verimli şekilde yerleştiren bir nesting (yuvalama) uygulaması. DXF dosyalarından parça geometrilerini okur, Rust tabanlı `lbf` motoruyla optimize yerleşim hesaplar ve sonuçları tekrar DXF olarak dışa aktarır.

## Neden bu proje?

Sac metal kesim işlerinde fire (atık) oranını düşürmek doğrudan maliyet tasarrufu sağlar. Parçaları elle yerleştirmek hem zaman alır hem de optimal sonuç vermez. Vega Nesting bu süreci otomatikleştirir:

- DXF dosyalarını sürükle-bırak ile yükle
- Plaka boyutlarını ve boşluk payını ayarla
- Arka planda nesting hesaplasın, sen başka işinle ilgilen
- Sonuç DXF dosyalarını indir, doğrudan kesim makinesine gönder

## Teknik Özet

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python 3.11 + FastAPI |
| Nesting motoru | `lbf` (Rust, [jagua-rs](https://github.com/VovaStelmashchuk/jagua-rs) tabanlı) |
| Geometri işleme | Shapely + ezdxf |
| Veritabanı | SQLite |
| Arayüz | Jinja2 template + vanilla JS |
| Konteyner | Docker (multi-stage build) |

## Nasıl Çalışır

1. Kullanıcı DXF dosyaları yükler → `ezdxf` ile parse edilir, kapalı poligonlara dönüştürülür
2. Parça geometrilerine `shapely` ile buffer uygulanır (boşluk payı)
3. `lbf` motoruna JSON input olarak verilir → Rust tarafında optimal yerleşim hesaplanır
4. Sonuç koordinatları ile her parça DXF üzerinde konumlandırılır
5. Kullanıcı sonuç DXF dosyalarını indirir

## Kurulum

### Gereksinimler

- Python 3.11+
- Rust (sadece `lbf` motorunu derlemek için gerekli, Docker kullanıyorsanız otomatik)

### Yerel Kurulum

```bash
# Repoyu klonla
git clone https://github.com/sngzege/vega-nesting.git
cd vega-nesting/server

# Python bağımlılıkları
pip install -r app/requirements.txt

# lbf motorunu derle (Linux)
cd app
bash build_engine.sh
chmod +x lbf
cd ..

# Sunucuyu başlat
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Tarayıcıda `http://localhost:8000` adresine gidin.

### Docker ile Kurulum

```bash
cd server
docker compose up --build
```

Multi-stage Dockerfile önce Rust ile `lbf` motorunu derler, sonra Python runtime'a geçer. Tek komutla hazır.

## Kullanım

1. **Giriş yap** — kullanıcı adı ile oturum aç (SQLite'da saklanır)
2. **Proje oluştur** — plaka genişliği, yüksekliği ve boşluk payını belirle
3. **DXF yükle** — parçaları sürükle-bırak ile ekle, adet gir
4. **Hesapla** — nesting işlemi arka planda çalışır
5. **İndir** — sonuç DXF dosyalarını al

Projeler kaydedilir, daha sonra tekrar açılabilir.

## Proje Yapısı

```
vega-nesting/
├── server/
│   ├── app/
│   │   ├── main.py              # FastAPI uygulaması, endpoint'ler
│   │   ├── database.py          # SQLite veritabanı katmanı
│   │   ├── build_engine.sh      # lbf motoru derleme betiği
│   │   ├── requirements.txt     # Python bağımlılıkları
│   │   ├── nesting/
│   │   │   ├── engine.py        # Nesting iş akışı orchestrator
│   │   │   ├── build_geometry.py# DXF'ten Shapely geometri üretimi
│   │   │   ├── dxf_utils.py     # DXF okuma/temizleme yardımcıları
│   │   │   ├── dxf_parser.py    # DXF dosya ayrıştırıcı
│   │   │   ├── input_builder.py # lbf motoru için JSON input oluşturucu
│   │   │   └── svg_generator.py # SVG önizleme üreteci
│   │   ├── templates/           # Jinja2 HTML şablonları
│   │   ├── static/              # CSS, JS dosyaları
│   │   ├── uploads/             # Yüklenen DXF dosyaları
│   │   └── output/              # Hesaplanan sonuç dosyaları
│   ├── tests/                   # pytest testleri
│   ├── Dockerfile               # Multi-stage Docker build
│   └── docker-compose.yml       # Docker Compose konfigürasyonu
└── README.md
```

## API

| Endpoint | Yöntem | Açıklama |
|----------|--------|----------|
| `/` | GET | Ana sayfa (arayüz) |
| `/api/login` | POST | Kullanıcı girişi |
| `/api/projects` | POST | Yeni proje oluştur |
| `/api/projects/{id}` | GET | Proje detayı |
| `/api/projects/{id}/files` | POST | DXF dosyası yükle |
| `/api/projects/{id}/nest` | POST | Nesting hesaplaması başlat |
| `/api/jobs/{id}` | GET | Job durumu sorgula |

Swagger dokümantasyonu: `http://localhost:8000/docs`

## Testler

```bash
cd server/tests
pytest -v
```

Windows ortamında `lbf` binary'ine ihtiyaç yoktur, testler mock ile çalışır.

## Lisans

Henüz belirlenmedi.
