import { notFound } from "next/navigation";
import { getRoomsFinishes } from "@/lib/v2Db";
import RoomsFinishesBoard from "@/components/RoomsFinishesBoard";

export const dynamic = "force-dynamic";

export default async function V2RoomsPage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const data = await getRoomsFinishes(permit);
  if (!data) return notFound();
  return <RoomsFinishesBoard data={data} />;
}
