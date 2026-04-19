import { apiGet } from '@/lib/api-client';
import BrainClient, {
  BrainControlPlanePayload,
  DailyBriefEntry,
  PersonaDeltaEntry,
} from './BrainClient';
import { loadBrainDocIndex } from './docSources';
import { loadPersonaWorkspace } from './personaBundle';

export const dynamic = 'force-dynamic';
export const revalidate = 0;
const BRAIN_BOOTSTRAP_TIMEOUT_MS = 6_000;

type BrainInitialState = {
  briefs: DailyBriefEntry[];
  personaDeltas: PersonaDeltaEntry[];
  controlPlane: BrainControlPlanePayload | null;
};

export default async function BrainPage() {
  const docs = loadBrainDocIndex();
  const personaWorkspace = loadPersonaWorkspace();
  const initialState = await loadBrainInitialState();
  return <BrainClient docs={docs} personaWorkspace={personaWorkspace} initialState={initialState} />;
}

async function loadBrainInitialState(): Promise<BrainInitialState> {
  const requestTs = Date.now();
  const [briefsRes, personaRes, controlPlaneRes] = await Promise.allSettled([
    apiGet<DailyBriefEntry[]>(`/api/briefs/?limit=50&brain_bootstrap_ts=${requestTs}`, { timeoutMs: BRAIN_BOOTSTRAP_TIMEOUT_MS }),
    apiGet<PersonaDeltaEntry[]>(`/api/persona/deltas?limit=50&view=brain_queue&brain_bootstrap_ts=${requestTs}`, {
      timeoutMs: BRAIN_BOOTSTRAP_TIMEOUT_MS,
    }),
    apiGet<BrainControlPlanePayload>(`/api/brain/control-plane?brain_bootstrap_ts=${requestTs}`, {
      timeoutMs: BRAIN_BOOTSTRAP_TIMEOUT_MS,
    }),
  ]);

  return {
    briefs: briefsRes.status === 'fulfilled' && Array.isArray(briefsRes.value) ? briefsRes.value : [],
    personaDeltas: personaRes.status === 'fulfilled' && Array.isArray(personaRes.value) ? personaRes.value : [],
    controlPlane: controlPlaneRes.status === 'fulfilled' ? (controlPlaneRes.value ?? null) : null,
  };
}
