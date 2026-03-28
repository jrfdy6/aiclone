import type { DocEntry, PersonaWorkspace } from "./BrainClient";

export const workspaceSnapshot: { docs: DocEntry[]; personaWorkspace: PersonaWorkspace } = 
{
  "docs": [],
  "personaWorkspace": {
    "packs": [
      {
        "key": "linkedin",
        "title": "LinkedIn",
        "description": "Voice, proof points, wins, and active initiatives for public thought-leadership posts.",
        "sections": []
      },
      {
        "key": "outreach",
        "title": "Outreach",
        "description": "Audience-specific positioning, claims, and asks for email, DM, and partner outreach.",
        "sections": []
      },
      {
        "key": "podcast",
        "title": "Podcast / Interview",
        "description": "Long-form identity, philosophy, resume, story, and proof for interviews and conversations.",
        "sections": []
      }
    ],
    "pendingMarkdown": "",
    "health": {
      "bundlePath": "/Users/neo/.openclaw/workspace/knowledge/persona/feeze",
      "bundleVersion": "1.1",
      "personaId": "johnnie_fields",
      "missingFiles": [
        "identity/bio_facts.md",
        "identity/philosophy.md",
        "identity/VOICE_PATTERNS.md",
        "identity/audience_communication.md",
        "identity/decision_principles.md",
        "identity/claims.md",
        "prompts/content_guardrails.md",
        "prompts/outreach_playbook.md",
        "prompts/content_pillars.md",
        "prompts/channel_playbooks.md",
        "history/resume.md",
        "history/timeline.md",
        "history/initiatives.md",
        "history/wins.md",
        "history/story_bank.md",
        "inbox/pending_deltas.md"
      ],
      "missingFrontmatter": [],
      "todoFiles": [],
      "status": "error"
    }
  }
} as const;
