# Vega Nesting Server

Lightweight Python/FastAPI uygulaması ile 2D sac metal nesting. `jagua-rs` tabanlı `lbf` motorunu kullanır.

## Kurulum

### Gereksinimler
- Python 3.11+
- Rust (sadece `lbf` motorunu derlemek için)

### Adımlar

1. Bağımlılıkları yükleyin:
   ```bash
   cd app
   pip install -r requirements.txt
   ```

2. SQLite veritabanı otomatik oluşturulur (`app/vega_nesting.db`).

3. `lbf` motorunu derleyin (Linux'ta):
   ```bash
   cd app
   bash build_engine.sh
   chmod +x lbf
   ```
   Windows'ta test yaparken `lbf` binary'ine ihtiyaç yoktur; testler mock'ludur.

4. Sunucuyu başlatın:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   Yerel ağdan `http://sunucu_ip:8000` adresinden erişilebilir.

### Docker ile Kurulum

```bash
docker compose up --build
```

## Kullanım

- Tarayıcıda açılan arayüzden sheet boyutları, boşluk payı ve DXF parçaları yüklenir.
- Projeler kaydedilip tekrar açılabilir (SQLite ile kalıcı).
- Hesaplama bittikten sonra sonuç DXF dosyaları indirilir.

## Testler

Windows'ta tüm testler şu komutla çalıştırılır:

```bash
cd tests
pytest -v
```
