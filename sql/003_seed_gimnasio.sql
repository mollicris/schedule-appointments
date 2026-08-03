-- ============================================================================
--  Datos del módulo gimnasios: planes de membresía y cupos de clases grupales
-- ============================================================================
--  Idempotente: se puede correr varias veces. No borra ni sobrescribe planes
--  existentes (compara por nombre) y solo ajusta la capacidad de los servicios
--  listados más abajo.
--
--  Requisitos: haber corrido antes 001_schema_completo.sql (base nueva) o
--  002_upgrade_007_a_010.sql (base que ya venía del backend), y que el tenant
--  ya exista — se crea desde la app con el registro + wizard, no por SQL.
--
--  Para adaptarlo: cambiá v_business_name, los precios (en CENTAVOS) y los cupos.
-- ============================================================================

DO $$
DECLARE
    v_business_name  text := 'Gimnasio';   -- << nombre del negocio a configurar
    v_business_id    uuid;
    v_tenant_id      uuid;
    v_planes_nuevos  integer;
    v_cupos_ajustados integer;
BEGIN
    SELECT id, tenant_id
      INTO v_business_id, v_tenant_id
      FROM businesses
     WHERE name = v_business_name
       AND is_active
     LIMIT 1;

    IF v_business_id IS NULL THEN
        RAISE NOTICE 'No existe un negocio activo llamado "%". Registrá el tenant y completá el wizard primero; después volvé a correr este script.', v_business_name;
        RETURN;
    END IF;

    RAISE NOTICE 'Negocio: % (id=%)', v_business_name, v_business_id;

    -- ── Planes de membresía ─────────────────────────────────────────────────
    -- price está en CENTAVOS: 25000 = Bs 250. billing_period: monthly | quarterly | annual
    WITH nuevos AS (
        INSERT INTO membership_plans (
            id, tenant_id, business_id, name, description, price, billing_period, is_active
        )
        SELECT gen_random_uuid(), v_tenant_id, v_business_id,
               p.name, p.description, p.price, p.billing_period, true
          FROM (VALUES
                    ('Mensual',    'Acceso a clases grupales de lunes a sábado',      25000, 'monthly'),
                    ('Trimestral', 'Tres meses con 13% de descuento',                 65000, 'quarterly'),
                    ('Anual',      'Todo el año + evaluación física trimestral',     220000, 'annual')
                ) AS p(name, description, price, billing_period)
         WHERE NOT EXISTS (
                   SELECT 1
                     FROM membership_plans mp
                    WHERE mp.business_id = v_business_id
                      AND mp.name = p.name
               )
        RETURNING 1
    )
    SELECT count(*) INTO v_planes_nuevos FROM nuevos;

    RAISE NOTICE 'Planes creados: % (los que ya existían quedaron intactos)', v_planes_nuevos;

    -- ── Cupos de clases grupales ────────────────────────────────────────────
    -- capacity = 1 es servicio individual (comportamiento histórico).
    -- capacity > 1 lo vuelve clase grupal: los horarios se ofrecen cada
    -- duration_minutes y el aforo se cuenta por hora de inicio.
    WITH ajustados AS (
        UPDATE services s
           SET capacity = c.capacity,
               updated_at = now()
          FROM (VALUES
                    ('Yoga',         15),
                    ('Clase grupal', 20)
                ) AS c(name, capacity)
         WHERE s.business_id = v_business_id
           AND s.name = c.name
           AND s.capacity <> c.capacity
        RETURNING 1
    )
    SELECT count(*) INTO v_cupos_ajustados FROM ajustados;

    RAISE NOTICE 'Servicios con cupos ajustados: %', v_cupos_ajustados;
END $$;

-- ── Verificación ────────────────────────────────────────────────────────────
SELECT b.name AS negocio, mp.name AS plan, mp.price / 100 AS precio, mp.billing_period, mp.is_active
  FROM membership_plans mp
  JOIN businesses b ON b.id = mp.business_id
 ORDER BY b.name, mp.price;

SELECT b.name AS negocio,
       s.name AS servicio,
       s.duration_minutes,
       s.capacity,
       CASE WHEN s.capacity > 1 THEN 'clase grupal' ELSE 'individual' END AS tipo
  FROM services s
  JOIN businesses b ON b.id = s.business_id
 WHERE s.is_active
 ORDER BY b.name, s.capacity DESC, s.name;
