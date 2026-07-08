import { Pool } from "pg";

// Reuse one pool across hot-reloads in dev.
declare global {
  // eslint-disable-next-line no-var
  var _pgPool: Pool | undefined;
}

function poolConfig() {
  // Strip SSL query params so pg doesn't warn about aliasing `sslmode` to
  // `verify-full`; set SSL explicitly on the pool instead.
  const raw = process.env.NEON_DATABASE_URL!;
  let connectionString = raw;
  try {
    const u = new URL(raw);
    for (const k of ["sslmode", "channel_binding", "ssl"]) u.searchParams.delete(k);
    connectionString = u.toString();
  } catch {
    /* leave as-is if not a parseable URL */
  }
  return { connectionString, ssl: { rejectUnauthorized: false }, max: 5 };
}

export const pool = global._pgPool ?? new Pool(poolConfig());

if (process.env.NODE_ENV !== "production") global._pgPool = pool;

export async function q<T = Record<string, unknown>>(
  text: string,
  params?: unknown[]
): Promise<T[]> {
  const r = await pool.query(text, params);
  return r.rows as T[];
}
