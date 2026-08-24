import OpsClient, { type ExecutiveFeed } from './OpsClient';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const EMPTY_EXECUTIVE_FEED: ExecutiveFeed = {
  artifacts: [],
  chronicleEntries: [],
  standupPreps: [],
  pmRecommendations: [],
};

/**
 * Ops hydrates only from its authenticated, bounded control-plane APIs.
 * Repository and private runtime files must never become React page props.
 */
export default function OpsPage() {
  return <OpsClient workspaceFiles={[]} docEntries={[]} executiveFeed={EMPTY_EXECUTIVE_FEED} />;
}
