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

-- Columna + índice único para el upsert de deduplicación
-- (studio_id, raw_class_id, scraped_date) evita duplicar clases al re-correr el scraper el mismo día
-- scraped_date la llena la app (fecha en America/Mexico_City), no se calcula en la BD
-- porque las conversiones de timezone en Postgres no son "immutable" y no sirven en columnas generadas
ALTER TABLE snapshots
  ADD COLUMN scraped_date DATE NOT NULL DEFAULT CURRENT_DATE;

CREATE UNIQUE INDEX idx_snapshots_dedup
  ON snapshots (studio_id, raw_class_id, scraped_date);

-- Estudios (ej. BUQ/GAFA) bloquean spots para reservar cupo a Gympass/Totalpass y no los liberan
-- después de que la clase pasa. `available` de la API ya descuenta esos bloqueos, `reservation_count` no.
-- blocked = lugares bloqueados (capacity - reserved - available)
-- apparent_occupancy_pct = ocupación "aparente" que ve el cliente (reservas + bloqueos) / capacity
-- occupancy_pct sigue siendo solo reservas reales / capacity
ALTER TABLE snapshots
  ADD COLUMN blocked INTEGER,
  ADD COLUMN apparent_occupancy_pct NUMERIC(5,2);

-- RLS
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE studios ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read snapshots"
  ON snapshots FOR SELECT TO authenticated USING (true);

CREATE POLICY "Service role can insert snapshots"
  ON snapshots FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Authenticated users can read studios"
  ON studios FOR SELECT TO authenticated USING (true);
