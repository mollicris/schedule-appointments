-- ============================================================================
--  OPCIONAL — Solo si vas a consultar la base con roles que NO son el dueño
--  de las tablas (por ejemplo la API de Supabase con anon / authenticated).
-- ============================================================================
--  Las políticas que crean las migraciones usan:
--
--      current_setting('app.current_tenant_id')::uuid
--
--  Si esa variable no está definida en la sesión, Postgres NO devuelve vacío:
--  lanza el error 42704 «unrecognized configuration parameter». Hoy eso no se
--  nota porque el backend conecta con el rol dueño de las tablas, y el dueño
--  omite RLS. Pero cualquier consulta desde PostgREST con anon/authenticated
--  fallaría en seco.
--
--  Este script recrea las mismas políticas con el segundo argumento en true
--  (missing_ok), así una sesión sin tenant simplemente no ve filas en lugar de
--  reventar. No cambia el aislamiento: sigue comparando tenant_id.
--
--  Nota: el backend nunca setea app.current_tenant_id (bind_tenant_to_session
--  existe pero no se invoca). El aislamiento real lo aplica cada repositorio
--  con su WHERE tenant_id = ... Estas políticas son defensa en profundidad.
-- ============================================================================

DO $$
DECLARE
    t text;
    tablas text[] := ARRAY[
        'users', 'businesses', 'services', 'professionals', 'business_hours',
        'clients', 'appointments', 'conversations', 'messages',
        'service_professionals',
        'membership_plans', 'membership_plan_services', 'memberships',
        'campaign_sends'
    ];
BEGIN
    FOREACH t IN ARRAY tablas LOOP
        IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = t) THEN
            RAISE NOTICE 'Tabla % no existe, se omite', t;
            CONTINUE;
        END IF;

        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_select ON %I', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_insert ON %I', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_update ON %I', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_delete ON %I', t);

        EXECUTE format($f$
            CREATE POLICY tenant_isolation_select ON %I
            FOR SELECT
            USING (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
        $f$, t);

        EXECUTE format($f$
            CREATE POLICY tenant_isolation_insert ON %I
            FOR INSERT
            WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
        $f$, t);

        EXECUTE format($f$
            CREATE POLICY tenant_isolation_update ON %I
            FOR UPDATE
            USING (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
        $f$, t);

        EXECUTE format($f$
            CREATE POLICY tenant_isolation_delete ON %I
            FOR DELETE
            USING (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
        $f$, t);

        RAISE NOTICE 'Políticas recreadas en %', t;
    END LOOP;
END $$;

-- ── Verificación ────────────────────────────────────────────────────────────
SELECT tablename, count(*) AS politicas
  FROM pg_policies
 WHERE schemaname = 'public'
   AND policyname LIKE 'tenant_isolation%'
 GROUP BY tablename
 ORDER BY tablename;
