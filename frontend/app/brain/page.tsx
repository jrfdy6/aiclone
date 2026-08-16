import BrainClient from './BrainClient';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

type BrainPageSearchParams = {
  delta_id?: string | string[];
};

export default async function BrainPage({ searchParams }: { searchParams?: Promise<BrainPageSearchParams> }) {
  const resolvedSearchParams = await searchParams;
  const rawDeltaId = Array.isArray(resolvedSearchParams?.delta_id)
    ? resolvedSearchParams.delta_id[0]
    : resolvedSearchParams?.delta_id;
  const requestedDeltaId = rawDeltaId?.trim() || null;
  return <BrainClient initialState={{ requestedDeltaId }} />;
}
