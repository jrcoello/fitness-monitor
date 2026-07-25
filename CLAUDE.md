# Fitness Monitor Engine — CLAUDE.md

Este archivo es el contexto maestro para Claude Code. Léelo completo antes de escribir cualquier código.

---

## ¿Qué es este proyecto?

Sistema de inteligencia de mercado para el sector fitness boutique en México. Extrae datos de ocupación de clases (capacidad, reservados, disponibles) desde las APIs de plataformas de reservas, los almacena en Supabase y los expone en un dashboard web privado.

**Fase MVP (alcance actual):**
- Scrapers: BUQ (200 estudios) + Mariana Tek (Commando, Zuda)
- Storage: Supabase / PostgreSQL
- Deploy: Render (cron jobs en nube) + dashboard estático
- Auth dashboard: login privado por cliente

---

## Stack tecnológico

- **Python 3.11+** — scrapers (requests)
- **Supabase** — PostgreSQL + Auth + API REST
- **Render** — cron jobs en nube (reemplaza Mac Mini para scrapers)
- **GitHub** — repo privado `fitness-monitor`, CI/CD con Render
- **HTML/CSS/JS vanilla** — dashboard (Chart.js) hosteado en Render Static

---

## Estructura del proyecto

```
fitness-monitor/
├── CLAUDE.md
├── README.md
├── .env                               ← NO subir a GitHub
├── .env.example                       ← SÍ subir
├── .gitignore
├── requirements.txt
├── config/
│   └── studios.json
├── scrapers/
│   ├── __init__.py
│   ├── buq.py
│   └── marianatek.py
├── core/
│   ├── __init__.py
│   ├── runner.py
│   ├── supabase_client.py
│   └── token_manager.py
├── supabase/
│   └── schema.sql
├── dashboard/
│   ├── index.html                     ← login
│   ├── app.html                       ← dashboard principal
│   ├── css/styles.css
│   └── js/
│       ├── auth.js
│       ├── dashboard.js
│       └── charts.js
└── render.yaml
```

---

## Schema Supabase (`supabase/schema.sql`)

```sql
-- Catálogo maestro de estudios
CREATE TABLE studios (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  platform        TEXT NOT NULL,
  city            TEXT,
  neighborhood    TEXT,
  brand_slug      TEXT,
  company_id      INTEGER,
  namespace       TEXT,
  location_id     INTEGER,
  active          BOOLEAN DEFAULT true,
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- Serie de tiempo — una fila por clase por corrida
CREATE TABLE snapshots (
  id              BIGSERIAL PRIMARY KEY,
  studio_id       TEXT REFERENCES studios(id),
  scraped_at      TIMESTAMPTZ NOT NULL,
  class_date      DATE NOT NULL,
  class_time      TIME NOT NULL,
  class_name      TEXT,
  coach           TEXT,
  location_name   TEXT,
  capacity        INTEGER,
  reserved        INTEGER,
  available       INTEGER,
  occupancy_pct   NUMERIC(5,2),
  platform        TEXT NOT NULL,
  raw_class_id    TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_snapshots_studio_date ON snapshots(studio_id, class_date);
CREATE INDEX idx_snapshots_scraped_at ON snapshots(scraped_at);
CREATE INDEX idx_snapshots_platform ON snapshots(platform);

-- RLS
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE studios ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read snapshots"
  ON snapshots FOR SELECT TO authenticated USING (true);

CREATE POLICY "Service role can insert snapshots"
  ON snapshots FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Authenticated users can read studios"
  ON studios FOR SELECT TO authenticated USING (true);
```

---

## Variables de entorno (`.env.example`)

```bash
# Supabase
SUPABASE_URL=https://{tu-proyecto}.supabase.co
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# BUQ
BUQ_EMAIL=
BUQ_PASSWORD=
BUQ_API_CLIENT=
BUQ_API_SECRET=

# Entorno
ENVIRONMENT=production
```

---

## `config/studios.json`

```json
{
  "studios": [
    {
      "id": "casa_onze_cdmx",
      "name": "Casa Onze CDMX",
      "platform": "buq",
      "city": "CDMX",
      "company_id": 146,
      "brand_slug": "cdmx",
      "locations": [259, 260, 261, 262, 263, 264, 270],
      "active": true
    },
    {
      "id": "commando_altavista",
      "name": "Commando Altavista",
      "platform": "marianatek",
      "city": "CDMX",
      "namespace": "commandostudio",
      "location_id": 48768,
      "region_id": 48574,
      "active": true
    },
    {
      "id": "zuda_lilas",
      "name": "Zuda Lilas",
      "platform": "marianatek",
      "city": "CDMX",
      "namespace": "zuda",
      "location_id": 48718,
      "active": true
    },
    {
      "id": "zuda_prado_norte",
      "name": "Zuda Prado Norte",
      "platform": "marianatek",
      "city": "CDMX",
      "namespace": "zuda",
      "location_id": 48717,
      "active": true
    },
    {
      "id": "zuda_artz",
      "name": "Zuda Artz Pedregal",
      "platform": "marianatek",
      "city": "CDMX",
      "namespace": "zuda",
      "location_id": 48719,
      "active": true
    }
  ]
}
```

---

## Lógica de scrapers

### BUQ (`scrapers/buq.py`)

**Golden nugget:** un token de Casa Onze funciona para los 200 estudios — solo cambiar el header `gafafit-company`.

**Auth flow:**
```python
POST https://buq.partners/oauth/token
{
  "grant_type": "password",
  "client_id": BUQ_API_CLIENT,
  "client_secret": BUQ_API_SECRET,
  "username": BUQ_EMAIL,
  "password": BUQ_PASSWORD,
  "scope": ""
}
→ Bearer token (duración ~1 año)
```

**Endpoint de meetings:**
```
GET https://buq.partners/api/brand/{brand_slug}/location/{location_id}/meetings
  ?only_actives=true
  &start={YYYY-M-D}       ← 7 días atrás
  &end={YYYY-M-D}         ← hoy
  &reducePopulation=true
Headers:
  Authorization: Bearer {token}
  gafafit-company: {company_id}
  Origin: https://casaonze.mx
```

**Mapeo de campos:**
- `id` → `raw_class_id`
- `capacity` → `capacity`
- `reservation_count` → `reserved`
- `available` → `available`
- `start` → `class_date` + `class_time` (convertir de UTC a Mexico_City)
- `type` → `class_name`
- `title` → `coach`

**Deduplicación:** upsert con conflicto en `(studio_id, raw_class_id, scraped_at::date)`.

### Mariana Tek (`scrapers/marianatek.py`)

**Sin auth. API pública.**

```
GET https://{namespace}.marianatek.com/api/customer/v1/classes
  ?min_start_date={today}
  &max_start_date={today+7}
  &page_size=500
  &location={location_id}
Headers:
  Accept: application/json
  Origin: https://{namespace}.marianaiframes.com
  Referer: https://{namespace}.marianaiframes.com/
```

**Mapeo de campos:**
- `id` → `raw_class_id`
- `available_spot_count` → `available`
- `capacity` → `capacity` (ignorar si = 0)
- `class_type.name` → `class_name`
- `instructors[0].name` → `coach`
- `classroom.name` → `location_name`
- `start_datetime` → `class_date` + `class_time`

**⚠️ Limitación conocida:** `capacity: 0` en clases pasadas. Solo guardar clases con `capacity > 0`.

---

## Runner (`core/runner.py`)

```python
def run(platform=None, studio_id=None, dry_run=False):
    studios = load_studios(platform, studio_id)
    token = get_buq_token()  # solo si hay estudios BUQ

    for studio in studios:
        try:
            if studio['platform'] == 'buq':
                snapshots = scrape_buq(studio, token)
            elif studio['platform'] == 'marianatek':
                snapshots = scrape_marianatek(studio)

            print(f"{studio['name']}: {len(snapshots)} clases encontradas")

            if not dry_run:
                saved = save_to_supabase(snapshots)
                print(f"{studio['name']}: {saved} clases guardadas")

        except Exception as e:
            print(f"ERROR {studio['name']}: {e}")
            continue  # no detener el loop por un estudio fallido
```

**CLI flags:**
```bash
python -m core.runner                          # todos los estudios
python -m core.runner --dry-run                # sin escribir a Supabase
python -m core.runner --platform buq           # solo BUQ
python -m core.runner --studio casa_onze_cdmx  # un solo estudio
```

---

## Cron jobs en Render (`render.yaml`)

```yaml
services:
  - type: cron
    name: fitness-scraper-hourly
    runtime: python
    buildCommand: pip install -r requirements.txt
    schedule: "30 * * * *"
    startCommand: python -m core.runner
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_KEY
        sync: false
      - key: BUQ_EMAIL
        sync: false
      - key: BUQ_PASSWORD
        sync: false
      - key: BUQ_API_CLIENT
        sync: false
      - key: BUQ_API_SECRET
        sync: false
      - key: ENVIRONMENT
        value: production
```

---

## Dashboard (`dashboard/`)

**Stack:** HTML + CSS + JS vanilla. Sin frameworks. Sin build step.

**Flujo:**
1. `index.html` — form de login → Supabase Auth JS SDK
2. Si autenticado → redirect a `app.html`
3. `app.html` consulta Supabase REST API con JWT del usuario autenticado

**Vistas MVP:**
- Ocupación promedio por estudio (última semana)
- Heatmap horario por día de semana
- Top clases por ocupación
- Comparativa entre estudios (BUQ vs Mariana Tek)

**Deploy:** Render Static Site conectado al mismo repo GitHub, carpeta `dashboard/`.

---

## Orden de construcción (seguir exactamente)

1. **Setup** — `requirements.txt`, `.gitignore`, `.env.example`
2. **Supabase** — ejecutar `supabase/schema.sql` en el SQL Editor de Supabase
3. **Core** — `supabase_client.py` + `token_manager.py`
4. **Scraper BUQ** — empezar con Casa Onze (1 estudio), validar en Supabase, luego expandir
5. **Scraper Mariana Tek** — empezar con Commando Altavista, validar
6. **Runner** — orquestador con flags CLI
7. **Prueba completa** — `python -m core.runner --dry-run`, revisar logs
8. **Dashboard** — login + vistas básicas
9. **Deploy** — push a GitHub → Render cron → Render Static dashboard

---

## Principios de desarrollo

- **Validar antes de escalar:** 1 estudio → funciona → todos los estudios
- **Upsert, nunca insert ciego:** `raw_class_id` como clave de deduplicación
- **Logs claros:** estudio | clases encontradas | clases guardadas | errores
- **Errores no detienen el loop:** try/except por estudio
- **Nunca hardcodear credenciales:** todo desde `.env`
- **Explicar antes de ejecutar:** Pato es no-técnico, pedir confirmación en decisiones importantes

---

## Archivos a subir al proyecto de Claude Code

| Archivo | Descripción |
|---|---|
| `CLAUDE.md` | Este archivo — contexto maestro |
| `FITNESS_MONITOR_ENGINE_RESEARCH.md` | Research técnico completo de todas las plataformas |
| `buq_brands.csv` | Directorio de 200 estudios BUQ con slugs y company_ids |

---

## Checklist de inicio

Antes de que Claude Code escriba la primera línea de código, confirmar:

- [ ] Proyecto Supabase creado → URL y keys en `.env`
- [ ] Repo GitHub privado `fitness-monitor` creado
- [ ] Los 3 archivos de contexto subidos al proyecto de Claude Code
- [ ] `supabase/schema.sql` ejecutado en Supabase SQL Editor
- [ ] Cuenta Render conectada a GitHub

---

## Estado del proyecto

- [x] Research de plataformas completado (14 abril 2026)
- [x] Directorio BUQ obtenido — 200 estudios (`buq_brands.csv`)
- [x] Credenciales BUQ validadas
- [x] Endpoints Mariana Tek mapeados y validados
- [x] Mac Mini M4 24GB adquirida
- [ ] Supabase — crear proyecto nuevo
- [ ] GitHub — crear repo privado
- [ ] Scraper BUQ
- [ ] Scraper Mariana Tek
- [ ] Runner + Supabase
- [ ] Dashboard
- [ ] Deploy Render
