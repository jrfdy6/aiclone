import { NextResponse } from "next/server";

export async function GET() {
 return NextResponse.json({
 status: "ok",
 service: "creative-ambition-ai-clone",
 timestamp: new Date().toISOString()
 });
}