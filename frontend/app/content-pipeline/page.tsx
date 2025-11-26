'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { apiFetch, getApiUrl } from '@/lib/api-client';

const API_URL = getApiUrl();

// Johnnie Fields Persona - from JOHNNIE_FIELDS_PERSONA.md
// Style Guide Reference - from CONTENT_STYLE_GUIDE.md
const STYLE_GUIDE = {
  voiceAndTone: [
    "Write like humans speak. Avoid corporate jargon and marketing fluff.",
    "Be confident and direct. Avoid softening phrases like 'I think,' 'maybe,' or 'could.'",
    "Use active voice instead of passive voice.",
    "Say 'you' more than 'we' when addressing external audiences.",
    "Use contractions for a warmer tone.",
  ],
  bannedWords: [
    "actually", "agile", "arguably", "battle tested", "best practices", "blazing fast",
    "business logic", "cognitive load", "delve", "disruptive", "facilitate", "game-changing",
    "innovative", "just", "leverage", "mission-critical", "modern", "numerous", "out of the box",
    "performant", "robust", "seamless", "utilize", "webinar",
  ],
  bannedPhrases: [
    "I think/I believe/we believe", "it seems", "sort of/kind of", "pretty much",
    "By developers, for developers", "We can't wait to see what you'll build",
    "The future of ___", "Today, we're excited to",
  ],
  llmPatternsToAvoid: [
    "Don't start with 'Great question!' or 'Let me help you.'",
    "Skip 'Let's dive into...' and 'In today's fast-paced digital world'",
    "Avoid 'In conclusion,' 'Overall,' or 'To summarize.'",
    "Don't end with 'Hope this helps!'",
    "Avoid hedge words: 'might,' 'perhaps,' 'potentially'",
  ],
  numbersAndData: [
    "Spell out one through nine, use numerals for 10+",
    "Round large numbers (2.3M vs 2,347,892)",
    "Always cite sources for statistics",
  ],
};

const PERSONA = {
  name: "Johnnie Fields",
  title: "Director of Admissions at Fusion Academy (DC)",
  positioning: "10+ years in education (AmeriCorps, 2U, Catholic University). Managed $34M portfolios and teams of 15+. Neurodivergent professional helping neurodivergent students. Georgetown Data Science cert, USC Master's in Tech/Business/Design. Building Easy Outfit fashion app. Son of a mechanic from St. Louis.",
  tone: "Expert + direct, inspiring. Like a top-tier operator who's also rooting for you. Process Champion energy.",
  writingStyle: "Clear, direct, practical. No fluffy language or jargon. Confident but not arrogant. Vulnerable when appropriate. Work-in-progress energy.",
  northStar: "I can't be put into a box. I'm a work in progress, pivoting into tech and data while leveraging 10+ years in education.",
  brandVoice: "911 Formula: 9 value posts, 1 sales, 1 personal. Be authentically me. When I sell, sell unabashedly. Show the journey, not just the wins.",
  coreBeliefs: [
    "There are only 3 things you can influence: People, Process, and Culture.",
    "Teams don't perform because they don't have a clear goal or they don't believe in the plan.",
    "I'm going to be the manager that solves the problem before it becomes big."
  ],
  industryFocus: ["K-12 Education", "EdTech", "Neurodivergent Support", "Mental Health Professionals", "Treatment Centers", "Private Schools"],
  uniqueValue: "Bridge Builder: Education veteran actively pivoting to tech. Lived Experience: Neurodivergent professional serving neurodivergent students. Operator + Builder: Not just using AI - building products with it.",
};

type ContentType = 'cold_email' | 'linkedin_post' | 'linkedin_dm' | 'instagram_post';
type ContentStatus = 'draft' | 'ready' | 'sent' | 'scheduled';

type ContentItem = {
  id: string;
  type: ContentType;
  title: string;
  content: string;
  prospect_id?: string;
  prospect_name?: string;
  status: ContentStatus;
  created_at: string;
  scheduled_for?: string;
  tags?: string[];
};

const CONTENT_TYPES: { value: ContentType; label: string; icon: string; color: string }[] = [
  { value: 'cold_email', label: 'Cold Email', icon: '📧', color: 'bg-blue-500' },
  { value: 'linkedin_post', label: 'LinkedIn Post', icon: '📝', color: 'bg-sky-500' },
  { value: 'linkedin_dm', label: 'LinkedIn DM', icon: '💬', color: 'bg-indigo-500' },
  { value: 'instagram_post', label: 'Instagram Post', icon: '📸', color: 'bg-pink-500' },
];

const STATUS_OPTIONS: { value: ContentStatus; label: string; color: string }[] = [
  { value: 'draft', label: 'Draft', color: 'bg-gray-100 text-gray-800' },
  { value: 'ready', label: 'Ready', color: 'bg-green-100 text-green-800' },
  { value: 'sent', label: 'Sent', color: 'bg-blue-100 text-blue-800' },
  { value: 'scheduled', label: 'Scheduled', color: 'bg-purple-100 text-purple-800' },
];

export default function ContentPipelinePage() {
  // Content library state
  const [contentItems, setContentItems] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Filters
  const [typeFilter, setTypeFilter] = useState<ContentType | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<ContentStatus | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Generator state
  const [showGenerator, setShowGenerator] = useState(false);
  const [generatorType, setGeneratorType] = useState<ContentType>('cold_email');
  const [generating, setGenerating] = useState(false);
  const [generatedContent, setGeneratedContent] = useState<string[]>([]);
  
  // Generator inputs
  const [prospectContext, setProspectContext] = useState('');
  const [topic, setTopic] = useState('');
  const [tone, setTone] = useState('professional');
  const [purpose, setPurpose] = useState('introduction');
  
  // Selection
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  
  // Style guide
  const [showStyleGuide, setShowStyleGuide] = useState(false);

  // Load saved content from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('content_pipeline');
    if (saved) {
      setContentItems(JSON.parse(saved));
    }
  }, []);

  // Save content to localStorage
  const saveContent = (items: ContentItem[]) => {
    setContentItems(items);
    localStorage.setItem('content_pipeline', JSON.stringify(items));
  };

  const generateContent = async () => {
    setGenerating(true);
    setGeneratedContent([]);

    try {
      if (generatorType === 'cold_email') {
        const response = await apiFetch('/api/content/email', {
          method: 'POST',
          body: JSON.stringify({
            subject: topic || 'Introduction',
            recipient_type: prospectContext || 'business professional',
            purpose: purpose,
            tone: tone,
          }),
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.email) {
            setGeneratedContent([
              `Subject: ${data.email.subject}\n\n${data.email.body}`,
            ]);
          }
        } else {
          // Fallback to AI generation prompt
          generateWithPrompt();
        }
      } else {
        generateWithPrompt();
      }
    } catch (err) {
      generateWithPrompt();
    } finally {
      setGenerating(false);
    }
  };

  const generateWithPrompt = () => {
    // Generate content locally with templates
    const templates = getTemplates(generatorType, { prospectContext, topic, tone, purpose });
    setGeneratedContent(templates);
  };

  const getTemplates = (type: ContentType, inputs: any): string[] => {
    const { prospectContext, topic, tone } = inputs;
    const p = PERSONA;
    
    switch (type) {
      case 'cold_email':
        return [
          `Subject: Quick question about ${topic || 'neurodivergent student support'}\n\nHi ${prospectContext || 'there'},\n\nI'm ${p.name}, ${p.title}. I noticed you're working with ${topic || 'students who learn differently'} and wanted to reach out.\n\nI've spent 10+ years in education - from managing $34M portfolios at 2U to now serving neurodivergent students at Fusion Academy. I'm always looking to connect with professionals who share this mission.\n\nWould you be open to a quick conversation about how we might support each other's work?\n\nBest,\nJohnnie`,
          `Subject: Idea for ${prospectContext || 'your practice'}\n\nHi,\n\nI came across your work in ${topic || 'education/mental health'} and had a thought.\n\nAt Fusion Academy DC, we serve neurodivergent students with 1:1 instruction. I'm building referral relationships with professionals like yourself who work with families seeking alternative education options.\n\nI'd love to share what we're seeing and learn about your approach. No pitch - just genuine curiosity about potential collaboration.\n\nWorth a 15-minute call?\n\nBest,\nJohnnie Fields\nDirector of Admissions, Fusion Academy`,
          `Subject: ${topic || 'Supporting neurodivergent students'}\n\nHi ${prospectContext || 'there'},\n\nI'll keep this direct - I'm the Director of Admissions at Fusion Academy DC, and I'm reaching out to build relationships with professionals who serve neurodivergent students and their families.\n\nMy background: 10+ years in education, Georgetown Data Science cert, and I'm neurodivergent myself. This work is personal.\n\nIf you ever have families looking for alternative education options, I'd love to be a resource. Either way, wishing you continued success in your work.\n\nJohnnie`,
        ];
      
      case 'linkedin_post':
        return [
          `🎯 ${topic || 'Here\'s what I learned this week about neurodivergent education'}:\n\nAfter 10+ years in education - from AmeriCorps to managing $34M portfolios at 2U to now Fusion Academy - I've learned one thing:\n\nThere are only 3 things you can influence: People, Process, and Culture.\n\n${prospectContext || 'Working with neurodivergent students'} has reinforced this:\n\n1️⃣ PEOPLE: Meet students where they are, not where you think they should be\n2️⃣ PROCESS: Systems that flex for different learning styles\n3️⃣ CULTURE: An environment where "different" is the norm\n\nI can't be put into a box. Neither can our students.\n\nWhat's your experience with ${topic || 'alternative education'}? 👇\n\n#Education #Neurodivergent #Leadership #EdTech`,
          `I used to think ${topic || 'success in education'} was about following the traditional path.\n\nI was wrong.\n\nAfter 10+ years - AmeriCorps, 2U, Catholic University, now Fusion Academy - here's what actually moves the needle:\n\n→ Relationships first. Power moves damage trust.\n→ Be the last to speak. Results in heavier adoption of ideas.\n→ Solve problems before they become big.\n\nI'm a work in progress. Son of a mechanic from St. Louis who fell in love with fashion in a random textile course. Now I'm pivoting into tech while serving neurodivergent students.\n\nCan't be put in a box. Neither can you.\n\nAgree or disagree? 👇`,
          `📊 Hot take: ${topic || 'Most education advice misses the point'}.\n\nTeams don't perform because:\n• They don't have a clear goal, OR\n• They don't believe in the plan\n\nThat's it. Everything else is noise.\n\nAt Fusion Academy, we serve neurodivergent students 1:1. The "traditional" approach doesn't work for everyone. And that's okay.\n\nI'm neurodivergent myself. This isn't just a job - it's personal.\n\nWhat I've learned:\n• Process Champion > Hero Ball\n• Constructive dialogue > Power moves\n• Temperature gauge your team - never let them cool off\n\nThoughts? What's worked in your experience?\n\n#Leadership #Education #Neurodivergent #ProcessChampion`,
        ];
      
      case 'linkedin_dm':
        return [
          `Hi ${prospectContext || 'there'}!\n\nI'm Johnnie, Director of Admissions at Fusion Academy DC. I came across your profile and was impressed by your work with ${topic || 'students/families'}.\n\nI'm building relationships with professionals in the ${topic || 'education/mental health'} space. At Fusion, we serve neurodivergent students with 1:1 instruction - and I'm always looking for referral partners who share this mission.\n\nWould you be open to connecting? No pitch, just exploring potential synergy.`,
          `Hey ${prospectContext || 'there'},\n\nLoved your recent post about ${topic || 'education'}. Really resonated with me.\n\nI've spent 10+ years in education and I'm now at Fusion Academy DC serving neurodivergent students. I'm also neurodivergent myself - this work is personal.\n\nAlways looking to connect with others in this space. Would love to learn more about your approach.\n\nOpen to a quick chat sometime?`,
          `Hi ${prospectContext || 'there'},\n\nI noticed we're both passionate about ${topic || 'supporting students who learn differently'}.\n\nI'm Johnnie - Director of Admissions at Fusion Academy DC (1:1 school for neurodivergent students). Background in data science and 10+ years in education.\n\nI'm building my referral network with mental health professionals, treatment centers, and private school admins. Would love to learn about your work and see if there's a way to support each other.\n\nWorth connecting?`,
        ];
      
      case 'instagram_post':
        return [
          `✨ ${topic || 'Real talk about education'} ✨\n\nI can't be put into a box.\n\nSon of a mechanic from St. Louis. Fell in love with fashion in a random textile course. 10+ years in education. Now pivoting into tech.\n\nNeurodivergent professional helping neurodivergent students.\n\nThe truth? Most people try to fit into someone else's mold. But here's the secret...\n\nYour "different" is your superpower. 💪\n\nSave this for later! 📌\n\n.\n.\n.\n#Neurodivergent #Education #WorkInProgress #CantBePutInABox`,
          `POV: You finally figured out ${topic || 'your path'} 🎯\n\nMe at 22: Following the "traditional" path\nMe at 32: Director of Admissions, building tech, can't be put in a box\n\nHere's what changed everything:\n\n1. Stopped trying to fit the mold\n2. Leaned into what makes me different\n3. Found work that's personal (I'm neurodivergent too)\n\nDrop a 🔥 if you've had to forge your own path!\n\n#CareerPivot #Neurodivergent #Education #BuildInPublic`,
          `${topic || 'This philosophy'} changed my leadership 👇\n\nThere are only 3 things you can influence:\n\n✅ People\n✅ Process  \n✅ Culture\n\nThat's it. Everything else is noise.\n\nI learned this managing $34M portfolios and teams of 15+. Now I apply it serving neurodivergent students at Fusion Academy.\n\nWant the full breakdown? Comment "YES" 💬\n\n#Leadership #Education #ProcessChampion #Mindset`,
        ];
      
      default:
        return ['Generated content will appear here...'];
    }
  };

  const saveGeneratedContent = (content: string, index: number) => {
    const newItem: ContentItem = {
      id: `content_${Date.now()}_${index}`,
      type: generatorType,
      title: content.split('\n')[0].slice(0, 50) + (content.split('\n')[0].length > 50 ? '...' : ''),
      content: content,
      status: 'draft',
      created_at: new Date().toISOString(),
      tags: [topic].filter(Boolean),
    };
    
    saveContent([newItem, ...contentItems]);
    setGeneratedContent(prev => prev.filter((_, i) => i !== index));
  };

  const updateItemStatus = (id: string, status: ContentStatus) => {
    saveContent(contentItems.map(item => 
      item.id === id ? { ...item, status } : item
    ));
  };

  const updateItemContent = (id: string) => {
    saveContent(contentItems.map(item => 
      item.id === id ? { ...item, content: editContent } : item
    ));
    setEditingItem(null);
    setEditContent('');
  };

  const deleteItem = (id: string) => {
    saveContent(contentItems.filter(item => item.id !== id));
  };

  const copyToClipboard = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  // Filter content
  const filteredContent = useMemo(() => {
    return contentItems.filter(item => {
      if (typeFilter !== 'all' && item.type !== typeFilter) return false;
      if (statusFilter !== 'all' && item.status !== statusFilter) return false;
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        if (!item.title.toLowerCase().includes(query) && 
            !item.content.toLowerCase().includes(query)) {
          return false;
        }
      }
      return true;
    });
  }, [contentItems, typeFilter, statusFilter, searchQuery]);

  const stats = useMemo(() => ({
    total: contentItems.length,
    drafts: contentItems.filter(i => i.status === 'draft').length,
    ready: contentItems.filter(i => i.status === 'ready').length,
    sent: contentItems.filter(i => i.status === 'sent').length,
  }), [contentItems]);

  const getTypeInfo = (type: ContentType) => CONTENT_TYPES.find(t => t.value === type)!;
  const getStatusInfo = (status: ContentStatus) => STATUS_OPTIONS.find(s => s.value === status)!;

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-[1400px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="flex items-center gap-3">
                <Link href="/" className="text-gray-400 hover:text-gray-600">←</Link>
                <h1 className="text-2xl font-bold text-gray-900">Content Pipeline</h1>
              </div>
              <p className="text-sm text-gray-500 mt-1">Generate and manage outreach content</p>
            </div>
            <button
              onClick={() => setShowGenerator(!showGenerator)}
              className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:from-blue-700 hover:to-indigo-700 font-medium"
            >
              {showGenerator ? 'Hide Generator' : '+ Generate Content'}
            </button>
          </div>

          {/* Quick Stats */}
          <div className="flex items-center gap-6 text-sm">
            <span className="text-gray-600">{stats.total} total</span>
            <span className="text-gray-500">|</span>
            <span className="text-gray-600">{stats.drafts} drafts</span>
            <span className="text-green-600">{stats.ready} ready</span>
            <span className="text-blue-600">{stats.sent} sent</span>
          </div>
        </div>
      </div>

      <div className="max-w-[1400px] mx-auto px-6 py-6">
        {/* Persona Context */}
        <div className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-xl p-4 mb-6 text-white">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg font-semibold">{PERSONA.name}</span>
                <span className="text-xs px-2 py-0.5 bg-blue-500/30 rounded">Persona Active</span>
              </div>
              <p className="text-sm text-gray-300">{PERSONA.title}</p>
              <p className="text-xs text-gray-400 mt-2 max-w-2xl">{PERSONA.northStar}</p>
            </div>
            <div className="text-right text-xs text-gray-400">
              <div>Tone: {PERSONA.tone.split('.')[0]}</div>
              <div className="mt-1">911 Formula: 9 value, 1 sales, 1 personal</div>
              <button
                onClick={() => setShowStyleGuide(!showStyleGuide)}
                className="mt-2 text-blue-300 hover:text-blue-200 underline"
              >
                {showStyleGuide ? 'Hide Style Guide' : 'View Style Guide'}
              </button>
            </div>
          </div>
        </div>

        {/* Style Guide Reference */}
        {showStyleGuide && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-amber-900">📝 Content Style Guide</h3>
              <span className="text-xs text-amber-600">Reference: CONTENT_STYLE_GUIDE.md</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              <div>
                <h4 className="font-medium text-amber-800 mb-2">Voice & Tone</h4>
                <ul className="space-y-1 text-amber-700">
                  {STYLE_GUIDE.voiceAndTone.map((item, i) => (
                    <li key={i} className="text-xs">• {item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="font-medium text-amber-800 mb-2">Avoid LLM Patterns</h4>
                <ul className="space-y-1 text-amber-700">
                  {STYLE_GUIDE.llmPatternsToAvoid.map((item, i) => (
                    <li key={i} className="text-xs">• {item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="font-medium text-amber-800 mb-2">Numbers & Data</h4>
                <ul className="space-y-1 text-amber-700">
                  {STYLE_GUIDE.numbersAndData.map((item, i) => (
                    <li key={i} className="text-xs">• {item}</li>
                  ))}
                </ul>
              </div>
              <div className="md:col-span-2 lg:col-span-3">
                <h4 className="font-medium text-amber-800 mb-2">Banned Words & Phrases</h4>
                <div className="flex flex-wrap gap-1">
                  {[...STYLE_GUIDE.bannedWords, ...STYLE_GUIDE.bannedPhrases].map((word, i) => (
                    <span key={i} className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">
                      {word}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Generator Panel */}
        {showGenerator && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Generate New Content</h2>
            
            {/* Content Type Selector */}
            <div className="flex gap-2 mb-6">
              {CONTENT_TYPES.map(type => (
                <button
                  key={type.value}
                  onClick={() => setGeneratorType(type.value)}
                  className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
                    generatorType === type.value
                      ? `${type.color} text-white`
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  <span>{type.icon}</span>
                  <span>{type.label}</span>
                </button>
              ))}
            </div>

            {/* Generator Inputs */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {generatorType === 'cold_email' || generatorType === 'linkedin_dm' ? 'Prospect/Recipient' : 'Context'}
                </label>
                <input
                  type="text"
                  value={prospectContext}
                  onChange={(e) => setProspectContext(e.target.value)}
                  placeholder={generatorType === 'cold_email' ? 'e.g., Marketing Director at SaaS company' : 'e.g., My experience with...'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Topic/Subject</label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g., AI automation, productivity tips"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tone</label>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="professional">Professional</option>
                  <option value="casual">Casual</option>
                  <option value="friendly">Friendly</option>
                  <option value="urgent">Urgent</option>
                  <option value="humorous">Humorous</option>
                </select>
              </div>
              {(generatorType === 'cold_email' || generatorType === 'linkedin_dm') && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Purpose</label>
                  <select
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="introduction">Introduction</option>
                    <option value="follow_up">Follow-up</option>
                    <option value="value_add">Value Add</option>
                    <option value="meeting_request">Meeting Request</option>
                    <option value="reconnect">Reconnect</option>
                  </select>
                </div>
              )}
            </div>

            <button
              onClick={generateContent}
              disabled={generating}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
            >
              {generating ? 'Generating...' : `Generate ${getTypeInfo(generatorType).label} Options`}
            </button>

            {/* Generated Content */}
            {generatedContent.length > 0 && (
              <div className="mt-6 space-y-4">
                <h3 className="font-medium text-gray-900">Generated Options (click to save)</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {generatedContent.map((content, i) => (
                    <div
                      key={i}
                      className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm transition-all"
                    >
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap mb-4 max-h-48 overflow-y-auto">
                        {content}
                      </pre>
                      <div className="flex gap-2">
                        <button
                          onClick={() => saveGeneratedContent(content, i)}
                          className="flex-1 px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                        >
                          Save to Pipeline
                        </button>
                        <button
                          onClick={() => copyToClipboard(content)}
                          className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded text-sm hover:bg-gray-200"
                        >
                          Copy
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Filters */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <div className="flex flex-wrap items-center gap-4">
            <input
              type="text"
              placeholder="Search content..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 min-w-[200px] max-w-md px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as any)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Types</option>
              {CONTENT_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Status</option>
              {STATUS_OPTIONS.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Content Table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase w-10">Type</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Content</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase w-28">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase w-32">Created</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase w-40">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredContent.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-gray-500">
                    {contentItems.length === 0 ? (
                      <>No content yet. Click "Generate Content" to get started.</>
                    ) : (
                      <>No content matches your filters.</>
                    )}
                  </td>
                </tr>
              ) : (
                filteredContent.map(item => {
                  const typeInfo = getTypeInfo(item.type);
                  const statusInfo = getStatusInfo(item.status);
                  const isExpanded = expandedItem === item.id;
                  const isEditing = editingItem === item.id;
                  
                  return (
                    <>
                      <tr key={item.id} className={`hover:bg-gray-50 ${isExpanded ? 'bg-blue-50' : ''}`}>
                        <td className="px-4 py-4">
                          <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg ${typeInfo.color} text-white`}>
                            {typeInfo.icon}
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          <button
                            onClick={() => setExpandedItem(isExpanded ? null : item.id)}
                            className="text-left w-full"
                          >
                            <div className="font-medium text-gray-900 hover:text-blue-600 truncate max-w-xl">
                              {item.title}
                            </div>
                            <div className="text-sm text-gray-500 truncate max-w-xl">
                              {item.content.slice(0, 100)}...
                            </div>
                          </button>
                        </td>
                        <td className="px-4 py-4">
                          <select
                            value={item.status}
                            onChange={(e) => updateItemStatus(item.id, e.target.value as ContentStatus)}
                            className={`text-xs font-medium rounded-full px-2 py-1 border-0 ${statusInfo.color}`}
                          >
                            {STATUS_OPTIONS.map(s => (
                              <option key={s.value} value={s.value}>{s.label}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-500">
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => copyToClipboard(item.content)}
                              className="text-gray-600 hover:text-gray-800 text-sm"
                            >
                              Copy
                            </button>
                            <button
                              onClick={() => {
                                setEditingItem(item.id);
                                setEditContent(item.content);
                                setExpandedItem(item.id);
                              }}
                              className="text-blue-600 hover:text-blue-800 text-sm"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => deleteItem(item.id)}
                              className="text-red-600 hover:text-red-800 text-sm"
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${item.id}-expanded`} className="bg-blue-50">
                          <td colSpan={5} className="px-4 py-4">
                            {isEditing ? (
                              <div className="space-y-3">
                                <textarea
                                  value={editContent}
                                  onChange={(e) => setEditContent(e.target.value)}
                                  rows={10}
                                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                                <div className="flex gap-2">
                                  <button
                                    onClick={() => updateItemContent(item.id)}
                                    className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
                                  >
                                    Save Changes
                                  </button>
                                  <button
                                    onClick={() => {
                                      setEditingItem(null);
                                      setEditContent('');
                                    }}
                                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-300"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-white p-4 rounded-lg border">
                                {item.content}
                              </pre>
                            )}
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}

