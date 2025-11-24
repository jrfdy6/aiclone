'use client';

import { useState } from 'react';

type Persona = {
  id: string;
  name: string;
  outreach_tone: string;
  industry_focus: string;
  writing_style: string;
  brand_voice: string;
  use_cases: string[];
  positioning: string;
};

export default function PersonasPage() {
  const [persona, setPersona] = useState<Persona>({
    id: 'default',
    name: 'Default Persona',
    outreach_tone: 'Professional and friendly',
    industry_focus: 'EdTech, K-12 Education',
    writing_style: 'Clear, concise, value-driven',
    brand_voice: 'Expert but approachable',
    use_cases: ['B2B Outreach', 'Content Creation', 'Prospecting'],
    positioning: 'AI-powered solutions for education',
  });

  const [isEditing, setIsEditing] = useState(false);

  const handleSave = () => {
    // Save to backend
    setIsEditing(false);
    alert('Persona saved successfully!');
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AI Personas & Memory Profiles</h1>
          <p className="text-gray-600 mt-1">Configure your AI's voice, tone, and positioning</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">{persona.name}</h2>
            {!isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Edit
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Outreach Tone</label>
              {isEditing ? (
                <input
                  type="text"
                  value={persona.outreach_tone}
                  onChange={(e) => setPersona({ ...persona, outreach_tone: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2"
                />
              ) : (
                <p className="text-gray-900">{persona.outreach_tone}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Industry Focus</label>
              {isEditing ? (
                <input
                  type="text"
                  value={persona.industry_focus}
                  onChange={(e) => setPersona({ ...persona, industry_focus: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2"
                />
              ) : (
                <p className="text-gray-900">{persona.industry_focus}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Writing Style</label>
              {isEditing ? (
                <textarea
                  value={persona.writing_style}
                  onChange={(e) => setPersona({ ...persona, writing_style: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2"
                  rows={3}
                />
              ) : (
                <p className="text-gray-900">{persona.writing_style}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Brand Voice</label>
              {isEditing ? (
                <textarea
                  value={persona.brand_voice}
                  onChange={(e) => setPersona({ ...persona, brand_voice: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2"
                  rows={3}
                />
              ) : (
                <p className="text-gray-900">{persona.brand_voice}</p>
              )}
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">User Positioning</label>
              {isEditing ? (
                <textarea
                  value={persona.positioning}
                  onChange={(e) => setPersona({ ...persona, positioning: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2"
                  rows={3}
                />
              ) : (
                <p className="text-gray-900">{persona.positioning}</p>
              )}
            </div>
          </div>

          {isEditing && (
            <div className="flex justify-end space-x-3 pt-4 border-t">
              <button
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Save Changes
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

