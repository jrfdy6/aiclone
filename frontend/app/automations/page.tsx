'use client';

import { useState } from 'react';

type Trigger = {
  id: string;
  type: 'new_prospect' | 'research_complete' | 'followup_due' | 'high_fit' | 'file_ingested';
  label: string;
};

type Action = {
  id: string;
  type: 'generate_outreach' | 'add_calendar' | 'send_notification' | 'update_status' | 'run_firecrawl' | 'store_insight';
  label: string;
};

type AutomationStep = {
  id: string;
  type: 'trigger' | 'action';
  triggerType?: string;
  actionType?: string;
};

const triggers: Trigger[] = [
  { id: '1', type: 'new_prospect', label: 'New prospect added' },
  { id: '2', type: 'research_complete', label: 'Research task completed' },
  { id: '3', type: 'followup_due', label: 'Follow-up event due' },
  { id: '4', type: 'high_fit', label: 'High-fit prospect detected' },
  { id: '5', type: 'file_ingested', label: 'New file ingested' },
];

const actions: Action[] = [
  { id: '1', type: 'generate_outreach', label: 'Generate outreach message' },
  { id: '2', type: 'add_calendar', label: 'Add calendar event' },
  { id: '3', type: 'send_notification', label: 'Send notification' },
  { id: '4', type: 'update_status', label: 'Update prospect status' },
  { id: '5', type: 'run_firecrawl', label: 'Run Firecrawl' },
  { id: '6', type: 'store_insight', label: 'Store insight' },
];

export default function AutomationsPage() {
  const [steps, setSteps] = useState<AutomationStep[]>([]);
  const [automationName, setAutomationName] = useState('');
  const [isActive, setIsActive] = useState(false);

  const addTrigger = (trigger: Trigger) => {
    if (steps.find(s => s.type === 'trigger')) {
      alert('Only one trigger allowed per automation');
      return;
    }
    setSteps([{ id: Date.now().toString(), type: 'trigger', triggerType: trigger.type }, ...steps]);
  };

  const addAction = (action: Action) => {
    setSteps([...steps, { id: Date.now().toString(), type: 'action', actionType: action.type }]);
  };

  const removeStep = (id: string) => {
    setSteps(steps.filter(s => s.id !== id));
  };

  const getStepLabel = (step: AutomationStep) => {
    if (step.type === 'trigger' && step.triggerType) {
      return triggers.find(t => t.type === step.triggerType)?.label || '';
    }
    if (step.type === 'action' && step.actionType) {
      return actions.find(a => a.type === step.actionType)?.label || '';
    }
    return '';
  };

  const saveAutomation = () => {
    if (!automationName.trim()) {
      alert('Please enter an automation name');
      return;
    }
    if (!steps.find(s => s.type === 'trigger')) {
      alert('Please add a trigger');
      return;
    }
    if (!steps.find(s => s.type === 'action')) {
      alert('Please add at least one action');
      return;
    }
    alert('Automation saved successfully!');
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Automations Builder</h1>
          <p className="text-gray-600 mt-1">Create automated workflows with triggers and actions</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Automation Name</label>
            <input
              type="text"
              value={automationName}
              onChange={(e) => setAutomationName(e.target.value)}
              placeholder="e.g., Auto-analyze new prospects"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Triggers */}
            <div>
              <h3 className="font-semibold mb-3">Triggers</h3>
              <div className="space-y-2">
                {triggers.map(trigger => (
                  <button
                    key={trigger.id}
                    onClick={() => addTrigger(trigger)}
                    className="w-full text-left px-4 py-3 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
                  >
                    {trigger.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Steps */}
            <div>
              <h3 className="font-semibold mb-3">Workflow Steps</h3>
              <div className="space-y-2 min-h-[200px] border-2 border-dashed border-gray-300 rounded-lg p-4">
                {steps.length === 0 ? (
                  <p className="text-gray-500 text-sm text-center py-8">Drag triggers and actions here</p>
                ) : (
                  steps.map((step, index) => (
                    <div
                      key={step.id}
                      className="flex items-center justify-between px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg"
                    >
                      <div className="flex items-center space-x-3">
                        <span className="text-gray-500">{index + 1}.</span>
                        <span>{getStepLabel(step)}</span>
                        <span className="text-xs text-gray-500">
                          {step.type === 'trigger' ? '⚡' : '▶'}
                        </span>
                      </div>
                      <button
                        onClick={() => removeStep(step.id)}
                        className="text-red-600 hover:text-red-800"
                      >
                        ✕
                      </button>
                    </div>
                  ))
                )}
                {steps.length > 0 && steps[steps.length - 1].type === 'trigger' && (
                  <div className="text-center text-gray-500 text-sm py-2">↓</div>
                )}
              </div>
            </div>

            {/* Actions */}
            <div>
              <h3 className="font-semibold mb-3">Actions</h3>
              <div className="space-y-2">
                {actions.map(action => (
                  <button
                    key={action.id}
                    onClick={() => addAction(action)}
                    className="w-full text-left px-4 py-3 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 transition-colors"
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded"
              />
              <span>Automation Active</span>
            </label>
            <button
              onClick={saveAutomation}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Save Automation
            </button>
          </div>
        </div>

        {/* Prebuilt Recipes */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-bold mb-4">Prebuilt Recipes</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold mb-2">Auto-Analyze Prospect</h3>
              <p className="text-sm text-gray-600 mb-3">When new prospect is added → Analyze them → Create outreach message → Add follow-up event</p>
              <button className="text-blue-600 hover:underline text-sm">Use Recipe →</button>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold mb-2">Weekly Research Summary</h3>
              <p className="text-sm text-gray-600 mb-3">Every Monday morning → Run topic research → Summarize insights → Notify me</p>
              <button className="text-blue-600 hover:underline text-sm">Use Recipe →</button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

