import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export async function GET() {
  const db = getDb();
  const portfolio = db.prepare("SELECT * FROM portfolio WHERE id=1").get() as Record<string, unknown> | undefined;
  const openPositions = db
    .prepare(
      "SELECT * FROM trades WHERE settled=0 AND action='buy' ORDER BY timestamp DESC"
    )
    .all();
  const totalNews = db
    .prepare("SELECT COUNT(*) as count FROM news")
    .get() as { count: number };
  const totalSnapshots = db
    .prepare("SELECT COUNT(*) as count FROM market_snapshots")
    .get() as { count: number };
  const totalCycles = db
    .prepare("SELECT COUNT(*) as count FROM agent_logs")
    .get() as { count: number };

  return NextResponse.json({
    ...(portfolio ?? {}),
    open_positions: openPositions,
    total_news: totalNews?.count ?? 0,
    total_snapshots: totalSnapshots?.count ?? 0,
    total_cycles: totalCycles?.count ?? 0,
  });
}
