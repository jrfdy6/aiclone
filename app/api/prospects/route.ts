import { NextResponse } from "next/server";

export async function GET() {
 return NextResponse.json([
 {
 id: 1,
 name: "Acme Corp",
 status: "lead"
 },
 {
 id: 2,
 name: "Globex",
 status: "contacted"
 }
 ]);
}