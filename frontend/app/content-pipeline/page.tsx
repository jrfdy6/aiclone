'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { apiFetch, getApiUrl } from '@/lib/api-client';
import NavHeader from '@/components/NavHeader';

const API_URL = getApiUrl();

// Chris Do 911 Framework
const CHRIS_DO_911 = {
  value: {
    ratio: 9,
    description: 'Pure value. Teaching, insights, observations. No selling mixed in.',
    icon: '📚',
    color: 'from-blue-600 to-cyan-600',
    bgColor: 'bg-blue-900/30',
    borderColor: 'border-blue-500',
  },
  sales: {
    ratio: 1,
    description: 'Sell unabashedly. "I\'m building X. Here\'s how to get involved."',
    icon: '💰',
    color: 'from-green-600 to-emerald-600',
    bgColor: 'bg-green-900/30',
    borderColor: 'border-green-500',
  },
  personal: {
    ratio: 1,
    description: 'Personal/behind-the-scenes. The real me, struggles included.',
    icon: '🙋',
    color: 'from-purple-600 to-pink-600',
    bgColor: 'bg-purple-900/30',
    borderColor: 'border-purple-500',
  },
};

// PACER Framework for LinkedIn
const PACER_PILLARS = {
  problem: { label: 'Problem', description: 'Identify the pain point', icon: '🎯' },
  amplify: { label: 'Amplify', description: 'Make the problem feel urgent', icon: '📢' },
  credibility: { label: 'Credibility', description: 'Show why you\'re qualified', icon: '🏆' },
  educate: { label: 'Educate', description: 'Provide value and solutions', icon: '📖' },
  request: { label: 'Request', description: 'Clear call to action', icon: '👉' },
};

// Johnnie Fields Persona
const PERSONA = {
  name: "Johnnie Fields",
  title: "Director of Admissions at Fusion Academy (DC)",
  northStar: "I can't be put into a box. I'm a work in progress, pivoting into tech and data while leveraging 10+ years in education.",
  tone: "Expert + direct, inspiring. Process Champion energy.",
  coreBeliefs: [
    "There are only 3 things you can influence: People, Process, and Culture.",
    "Teams don't perform because they don't have a clear goal or they don't believe in the plan.",
  ],
};

type ContentCategory = 'value' | 'sales' | 'personal';
type ContentType = 'cold_email' | 'linkedin_post' | 'linkedin_dm' | 'instagram_post';
type ContentStatus = 'draft' | 'ready' | 'sent' | 'scheduled';

type ContentItem = {
  id: string;
  category: ContentCategory;
  type: ContentType;
  title: string;
  content: string;
  pacer_elements?: string[];
  status: ContentStatus;
  created_at: string;
  tags?: string[];
};

const CONTENT_TYPES: { value: ContentType; label: string; icon: string }[] = [
  { value: 'cold_email', label: 'Cold Email', icon: '📧' },
  { value: 'linkedin_post', label: 'LinkedIn Post', icon: '📝' },
  { value: 'linkedin_dm', label: 'LinkedIn DM', icon: '💬' },
  { value: 'instagram_post', label: 'Instagram Post', icon: '📸' },
];

export default function ContentPipelinePage() {
  const [contentItems, setContentItems] = useState<ContentItem[]>([]);
  const [activeCategory, setActiveCategory] = useState<ContentCategory>('value');
  const [showGenerator, setShowGenerator] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatedContent, setGeneratedContent] = useState<string[]>([]);
  
  // Generator inputs
  const [generatorType, setGeneratorType] = useState<ContentType>('linkedin_post');
  const [topic, setTopic] = useState('');
  const [context, setContext] = useState('');
  const [selectedPacer, setSelectedPacer] = useState<string[]>([]);
  
  const [expandedItem, setExpandedItem] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('content_pipeline_911');
    if (saved) {
      setContentItems(JSON.parse(saved));
    }
  }, []);

  const saveContent = (items: ContentItem[]) => {
    setContentItems(items);
    localStorage.setItem('content_pipeline_911', JSON.stringify(items));
  };

  const stats = useMemo(() => {
    const value = contentItems.filter(i => i.category === 'value').length;
    const sales = contentItems.filter(i => i.category === 'sales').length;
    const personal = contentItems.filter(i => i.category === 'personal').length;
    const total = value + sales + personal;
    return { value, sales, personal, total };
  }, [contentItems]);

  const getCategoryContent = (category: ContentCategory) => {
    return contentItems.filter(i => i.category === category);
  };

  const generateContent = async () => {
    setGenerating(true);
    
    try {
      // Call AI-powered content generation API
      const res = await apiFetch('/api/content-generation/generate', {
        method: 'POST',
        body: JSON.stringify({
          user_id: 'johnnie_fields', // TODO: Get from auth
          topic: topic || 'professional growth',
          context: context || '',
          content_type: generatorType,
          category: activeCategory,
          pacer_elements: selectedPacer.map(p => p.charAt(0).toUpperCase() + p.slice(1)),
          tone: 'expert_direct',
        }),
      });
      
      const response = await res.json();
      console.log('API Response:', response);
      
      if (response?.success && response?.options && response.options.length > 0) {
        setGeneratedContent(response.options);
      } else {
        console.log('API returned no options, using templates');
        // Fallback to templates if API fails
        const templates = getTemplates(activeCategory, generatorType, { topic, context, pacer: selectedPacer });
        setGeneratedContent(templates);
      }
    } catch (error) {
      console.error('Content generation error:', error);
      // Fallback to templates
      const templates = getTemplates(activeCategory, generatorType, { topic, context, pacer: selectedPacer });
      setGeneratedContent(templates);
    }
    
    setGenerating(false);
  };

  const getTemplates = (category: ContentCategory, type: ContentType, inputs: any): string[] => {
    const { topic, context, pacer } = inputs;
    const p = PERSONA;
    
    if (category === 'value') {
      if (type === 'linkedin_post') {
        return [
          `🎯 ${topic || 'Here\'s what I learned this week'}:\n\nAfter 10+ years in education - from AmeriCorps to managing $34M portfolios at 2U to now Fusion Academy - I've learned one thing:\n\nThere are only 3 things you can influence: People, Process, and Culture.\n\n${context || 'Working with neurodivergent students'} has reinforced this:\n\n1️⃣ PEOPLE: Meet students where they are\n2️⃣ PROCESS: Systems that flex for different learning styles\n3️⃣ CULTURE: An environment where "different" is the norm\n\nWhat's your experience? 👇\n\n#Education #Neurodivergent #Leadership`,
          `📊 Hot take: ${topic || 'Most advice misses the point'}.\n\nTeams don't perform because:\n• They don't have a clear goal, OR\n• They don't believe in the plan\n\nThat's it. Everything else is noise.\n\nAt Fusion Academy, we serve neurodivergent students 1:1. The "traditional" approach doesn't work for everyone.\n\nWhat I've learned:\n• Process Champion > Hero Ball\n• Constructive dialogue > Power moves\n• Temperature gauge your team\n\nThoughts?\n\n#Leadership #Education #ProcessChampion`,
          `I used to think ${topic || 'success'} was about following the traditional path.\n\nI was wrong.\n\nAfter 10+ years - AmeriCorps, 2U, Catholic University, now Fusion Academy - here's what actually moves the needle:\n\n→ Relationships first. Power moves damage trust.\n→ Be the last to speak.\n→ Solve problems before they become big.\n\nI'm a work in progress. Can't be put in a box. Neither can you.\n\nAgree or disagree? 👇`,
        ];
      } else if (type === 'cold_email') {
        return [
          `Subject: Quick question about ${topic || 'neurodivergent student support'}\n\nHi ${context || 'there'},\n\nI'm Johnnie Fields, Director of Admissions at Fusion Academy DC. I noticed you're working with ${topic || 'students who learn differently'} and wanted to reach out.\n\nI've spent 10+ years in education - from managing $34M portfolios at 2U to now serving neurodivergent students. I'm always looking to connect with professionals who share this mission.\n\nWould you be open to a quick conversation?\n\nBest,\nJohnnie`,
          `Subject: Idea for ${context || 'your practice'}\n\nHi,\n\nI came across your work in ${topic || 'education/mental health'} and had a thought.\n\nAt Fusion Academy DC, we serve neurodivergent students with 1:1 instruction. I'm building referral relationships with professionals who work with families seeking alternative education options.\n\nWorth a 15-minute call?\n\nBest,\nJohnnie Fields\nDirector of Admissions, Fusion Academy`,
        ];
      }
    } else if (category === 'sales') {
      return [
        `🚀 I'm building something.\n\nAfter 10+ years in education and pivoting into tech, I'm creating ${topic || 'Easy Outfit'} - ${context || 'a fashion app that helps you use what you have'}.\n\nWhy? I've always wanted to look good but sometimes missed the mark. This solves my own problem.\n\nLooking for:\n• Beta testers\n• Feedback from people who struggle with styling\n• Connections to fashion/tech folks\n\nDM me if interested. No pitch deck, just building.\n\n#BuildInPublic #Fashion #Tech`,
        `📣 Let me be direct.\n\nI consult on enrollment management and program launches. 10+ years experience. $34M portfolios. Salesforce migrations.\n\nIf you need help with:\n• Admissions process optimization\n• Team coaching and development\n• Pipeline management\n• Program launches\n\nLet's talk. DM me or comment below.\n\nNo fluff. Just results.\n\n#Consulting #Education #EnrollmentManagement`,
      ];
    } else if (category === 'personal') {
      return [
        `I can't be put into a box.\n\nSon of a mechanic from St. Louis.\nFell in love with fashion in a random textile course.\n10+ years in education.\nNow pivoting into tech.\nNeurodivergent professional helping neurodivergent students.\n\nI'm a work in progress. And that's the point.\n\nYou're witnessing my journey - the wins, the struggles, the evolution.\n\nWho else refuses to be defined by a single label? 👇\n\n#WorkInProgress #CantBePutInABox #Journey`,
        `I used to dominate conversations.\n\nI'd talk over people. Interrupt. Make sure my point was heard.\n\nIt made me appear intimidating. And honestly? It hurt my relationships.\n\nSo I changed.\n\nNow I make it my business to be the LAST person to talk.\n\nThe result? More fruitful exchanges. Heavier adoption of my ideas. Better relationships.\n\nGrowth isn't comfortable. But it's worth it.\n\nWhat's something you've had to unlearn? 👇`,
        `The InspireSTL story.\n\nMy first job out of college wasn't a job - it was a mission.\n\nI helped found a nonprofit to prepare underprivileged youth in St. Louis. I mentored 20+ students. ACT prep. Resume workshops. Mock interviews.\n\nLess than 20% would have made it to a 4-year university without intervention.\n\n100% were admitted.\n\nThat's when I fell in love with coaching and mentoring. That's why I'm still in education 10+ years later.\n\nSome things choose you.\n\n#Education #Mentoring #Purpose`,
      ];
    }
    
    return ['Generated content will appear here...'];
  };

  const saveGeneratedContent = (content: string, index: number) => {
    const newItem: ContentItem = {
      id: `content_${Date.now()}_${index}`,
      category: activeCategory,
      type: generatorType,
      title: content.split('\n')[0].slice(0, 50) + '...',
      content: content,
      pacer_elements: selectedPacer,
      status: 'draft',
      created_at: new Date().toISOString(),
      tags: [topic].filter(Boolean),
    };
    
    saveContent([newItem, ...contentItems]);
    setGeneratedContent(prev => prev.filter((_, i) => i !== index));
  };

  const deleteItem = (id: string) => {
    saveContent(contentItems.filter(item => item.id !== id));
  };

  const copyToClipboard = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const togglePacer = (element: string) => {
    if (selectedPacer.includes(element)) {
      setSelectedPacer(selectedPacer.filter(p => p !== element));
    } else {
      setSelectedPacer([...selectedPacer, element]);
    }
  };

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
            Content Pipeline
          </h1>
          <p style={{ color: '#9ca3af' }}>
            Chris Do 911 Framework: 9 Value • 1 Sales • 1 Personal
          </p>
        </div>

        {/* Persona Banner */}
        <div style={{
          background: 'linear-gradient(to right, #1e293b, #334155)',
          borderRadius: '12px',
          padding: '16px',
          marginBottom: '24px',
          border: '1px solid #475569',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span style={{ fontSize: '18px', fontWeight: 600, color: 'white' }}>{PERSONA.name}</span>
                <span style={{ fontSize: '12px', padding: '2px 8px', backgroundColor: 'rgba(59, 130, 246, 0.3)', borderRadius: '4px', color: '#93c5fd' }}>Persona Active</span>
              </div>
              <p style={{ fontSize: '14px', color: '#9ca3af' }}>{PERSONA.title}</p>
              <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '8px', maxWidth: '600px' }}>{PERSONA.northStar}</p>
            </div>
            <div style={{ textAlign: 'right', fontSize: '12px', color: '#6b7280' }}>
              <div>Tone: {PERSONA.tone}</div>
            </div>
          </div>
        </div>

        {/* 911 Framework Stats */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '16px',
          marginBottom: '24px',
        }}>
          {(['value', 'sales', 'personal'] as ContentCategory[]).map((cat) => {
            const info = CHRIS_DO_911[cat];
            const count = getCategoryContent(cat).length;
            const isActive = activeCategory === cat;
            
            return (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                style={{
                  padding: '20px',
                  borderRadius: '12px',
                  border: isActive ? `2px solid ${cat === 'value' ? '#3b82f6' : cat === 'sales' ? '#22c55e' : '#a855f7'}` : '2px solid #475569',
                  backgroundColor: isActive ? (cat === 'value' ? 'rgba(59, 130, 246, 0.1)' : cat === 'sales' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(168, 85, 247, 0.1)') : '#1e293b',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '32px' }}>{info.icon}</span>
                  <div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>{count}</div>
                    <div style={{ fontSize: '12px', color: '#9ca3af', textTransform: 'uppercase' }}>
                      {cat} ({info.ratio}x)
                    </div>
                  </div>
                </div>
                <p style={{ fontSize: '12px', color: '#6b7280' }}>{info.description}</p>
              </button>
            );
          })}
        </div>

        {/* Generator Toggle */}
        <button
          onClick={() => setShowGenerator(!showGenerator)}
          style={{
            width: '100%',
            padding: '16px',
            borderRadius: '12px',
            border: '2px dashed #475569',
            backgroundColor: 'transparent',
            color: '#9ca3af',
            fontSize: '16px',
            cursor: 'pointer',
            marginBottom: '24px',
          }}
        >
          {showGenerator ? '✕ Hide Generator' : `+ Generate ${activeCategory.charAt(0).toUpperCase() + activeCategory.slice(1)} Content`}
        </button>

        {/* Generator Panel */}
        {showGenerator && (
          <div style={{
            backgroundColor: '#1e293b',
            borderRadius: '12px',
            padding: '24px',
            marginBottom: '24px',
            border: '1px solid #475569',
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'white', marginBottom: '16px' }}>
              Generate {activeCategory.charAt(0).toUpperCase() + activeCategory.slice(1)} Content
            </h3>
            
            {/* Content Type */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '14px', color: '#9ca3af', marginBottom: '8px' }}>Content Type</label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {CONTENT_TYPES.map(type => (
                  <button
                    key={type.value}
                    onClick={() => setGeneratorType(type.value)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      border: 'none',
                      backgroundColor: generatorType === type.value ? '#3b82f6' : '#374151',
                      color: 'white',
                      cursor: 'pointer',
                      fontSize: '14px',
                    }}
                  >
                    {type.icon} {type.label}
                  </button>
                ))}
              </div>
            </div>

            {/* PACER Elements (for value content) */}
            {activeCategory === 'value' && (
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', color: '#9ca3af', marginBottom: '8px' }}>
                  PACER Framework Elements (optional)
                </label>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {Object.entries(PACER_PILLARS).map(([key, pillar]) => (
                    <button
                      key={key}
                      onClick={() => togglePacer(key)}
                      style={{
                        padding: '8px 12px',
                        borderRadius: '8px',
                        border: selectedPacer.includes(key) ? '2px solid #22c55e' : '1px solid #475569',
                        backgroundColor: selectedPacer.includes(key) ? 'rgba(34, 197, 94, 0.2)' : 'transparent',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: '12px',
                      }}
                    >
                      {pillar.icon} {pillar.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Inputs */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#9ca3af', marginBottom: '8px' }}>Topic</label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g., neurodivergent education, AI tools"
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '8px',
                    border: '1px solid #475569',
                    backgroundColor: '#0f172a',
                    color: 'white',
                    fontSize: '14px',
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#9ca3af', marginBottom: '8px' }}>Context</label>
                <input
                  type="text"
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  placeholder="e.g., prospect name, specific situation"
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '8px',
                    border: '1px solid #475569',
                    backgroundColor: '#0f172a',
                    color: 'white',
                    fontSize: '14px',
                  }}
                />
              </div>
            </div>

            <button
              onClick={generateContent}
              disabled={generating}
              style={{
                padding: '12px 24px',
                borderRadius: '8px',
                border: 'none',
                background: 'linear-gradient(to right, #3b82f6, #8b5cf6)',
                color: 'white',
                fontSize: '16px',
                fontWeight: 600,
                cursor: 'pointer',
                opacity: generating ? 0.5 : 1,
              }}
            >
              {generating ? 'Generating...' : 'Generate Options'}
            </button>

            {/* Generated Content */}
            {generatedContent.length > 0 && (
              <div style={{ marginTop: '24px' }}>
                <h4 style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '12px' }}>Generated Options</h4>
                <div style={{ display: 'grid', gap: '16px' }}>
                  {generatedContent.map((content, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '16px',
                        borderRadius: '8px',
                        backgroundColor: '#0f172a',
                        border: '1px solid #475569',
                      }}
                    >
                      <pre style={{
                        whiteSpace: 'pre-wrap',
                        fontSize: '14px',
                        color: '#e2e8f0',
                        marginBottom: '12px',
                        fontFamily: 'inherit',
                        maxHeight: '200px',
                        overflow: 'auto',
                      }}>
                        {content}
                      </pre>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          onClick={() => saveGeneratedContent(content, i)}
                          style={{
                            padding: '8px 16px',
                            borderRadius: '6px',
                            border: 'none',
                            backgroundColor: '#22c55e',
                            color: 'white',
                            fontSize: '14px',
                            cursor: 'pointer',
                          }}
                        >
                          Save to Pipeline
                        </button>
                        <button
                          onClick={() => copyToClipboard(content)}
                          style={{
                            padding: '8px 16px',
                            borderRadius: '6px',
                            border: '1px solid #475569',
                            backgroundColor: 'transparent',
                            color: '#9ca3af',
                            fontSize: '14px',
                            cursor: 'pointer',
                          }}
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

        {/* Content List for Active Category */}
        <div style={{
          backgroundColor: '#1e293b',
          borderRadius: '12px',
          border: '1px solid #475569',
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '16px 20px',
            borderBottom: '1px solid #475569',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'white' }}>
              {CHRIS_DO_911[activeCategory].icon} {activeCategory.charAt(0).toUpperCase() + activeCategory.slice(1)} Content
            </h3>
            <span style={{ fontSize: '14px', color: '#6b7280' }}>
              {getCategoryContent(activeCategory).length} items
            </span>
          </div>
          
          {getCategoryContent(activeCategory).length === 0 ? (
            <div style={{ padding: '48px', textAlign: 'center', color: '#6b7280' }}>
              No {activeCategory} content yet. Generate some above!
            </div>
          ) : (
            <div>
              {getCategoryContent(activeCategory).map((item) => (
                <div
                  key={item.id}
                  style={{
                    padding: '16px 20px',
                    borderBottom: '1px solid #374151',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span>{CONTENT_TYPES.find(t => t.value === item.type)?.icon}</span>
                        <span style={{ fontSize: '14px', fontWeight: 500, color: 'white' }}>{item.title}</span>
                      </div>
                      <p style={{ fontSize: '13px', color: '#9ca3af', marginBottom: '8px' }}>
                        {item.content.slice(0, 120)}...
                      </p>
                      {item.pacer_elements && item.pacer_elements.length > 0 && (
                        <div style={{ display: 'flex', gap: '4px' }}>
                          {item.pacer_elements.map(p => (
                            <span key={p} style={{
                              fontSize: '10px',
                              padding: '2px 6px',
                              backgroundColor: 'rgba(34, 197, 94, 0.2)',
                              color: '#86efac',
                              borderRadius: '4px',
                            }}>
                              {PACER_PILLARS[p as keyof typeof PACER_PILLARS]?.label}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        onClick={() => setExpandedItem(expandedItem === item.id ? null : item.id)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: '1px solid #475569',
                          backgroundColor: 'transparent',
                          color: '#9ca3af',
                          fontSize: '12px',
                          cursor: 'pointer',
                        }}
                      >
                        {expandedItem === item.id ? 'Hide' : 'View'}
                      </button>
                      <button
                        onClick={() => copyToClipboard(item.content)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: '1px solid #475569',
                          backgroundColor: 'transparent',
                          color: '#9ca3af',
                          fontSize: '12px',
                          cursor: 'pointer',
                        }}
                      >
                        Copy
                      </button>
                      <button
                        onClick={() => deleteItem(item.id)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: '1px solid #ef4444',
                          backgroundColor: 'transparent',
                          color: '#ef4444',
                          fontSize: '12px',
                          cursor: 'pointer',
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  {expandedItem === item.id && (
                    <div style={{
                      marginTop: '12px',
                      padding: '12px',
                      backgroundColor: '#0f172a',
                      borderRadius: '8px',
                    }}>
                      <pre style={{
                        whiteSpace: 'pre-wrap',
                        fontSize: '14px',
                        color: '#e2e8f0',
                        fontFamily: 'inherit',
                      }}>
                        {item.content}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
