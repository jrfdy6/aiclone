(()=>{var e={};e.id=406,e.ids=[406],e.modules={2934:e=>{"use strict";e.exports=require("next/dist/client/components/action-async-storage.external.js")},4580:e=>{"use strict";e.exports=require("next/dist/client/components/request-async-storage.external.js")},5869:e=>{"use strict";e.exports=require("next/dist/client/components/static-generation-async-storage.external.js")},399:e=>{"use strict";e.exports=require("next/dist/compiled/next-server/app-page.runtime.prod.js")},2534:(e,t,o)=>{"use strict";o.r(t),o.d(t,{GlobalError:()=>s.a,__next_app__:()=>u,originalPathname:()=>c,pages:()=>p,routeModule:()=>h,tree:()=>d}),o(4588),o(1506),o(5866);var n=o(3191),i=o(8716),r=o(7922),s=o.n(r),a=o(5231),l={};for(let e in a)0>["default","tree","pages","GlobalError","originalPathname","__next_app__","routeModule"].indexOf(e)&&(l[e]=()=>a[e]);o.d(t,l);let d=["",{children:["content-pipeline",{children:["__PAGE__",{},{page:[()=>Promise.resolve().then(o.bind(o,4588)),"/Users/johnniefields/Desktop/Cursor/aiclone/frontend/app/content-pipeline/page.tsx"]}]},{}]},{layout:[()=>Promise.resolve().then(o.bind(o,1506)),"/Users/johnniefields/Desktop/Cursor/aiclone/frontend/app/layout.tsx"],"not-found":[()=>Promise.resolve().then(o.t.bind(o,5866,23)),"next/dist/client/components/not-found-error"]}],p=["/Users/johnniefields/Desktop/Cursor/aiclone/frontend/app/content-pipeline/page.tsx"],c="/content-pipeline/page",u={require:o,loadChunk:()=>Promise.resolve()},h=new n.AppPageRouteModule({definition:{kind:i.x.APP_PAGE,page:"/content-pipeline/page",pathname:"/content-pipeline",bundlePath:"",filename:"",appPaths:[]},userland:{loaderTree:d}})},3705:(e,t,o)=>{Promise.resolve().then(o.bind(o,9116))},9142:()=>{},678:(e,t,o)=>{Promise.resolve().then(o.t.bind(o,2994,23)),Promise.resolve().then(o.t.bind(o,6114,23)),Promise.resolve().then(o.t.bind(o,9727,23)),Promise.resolve().then(o.t.bind(o,9671,23)),Promise.resolve().then(o.t.bind(o,1868,23)),Promise.resolve().then(o.t.bind(o,4759,23))},9116:(e,t,o)=>{"use strict";o.r(t),o.d(t,{default:()=>c});var n=o(326),i=o(7577),r=o(8528),s=o(5061);(0,r.kG)();let a={value:{ratio:9,description:"Pure value. Teaching, insights, observations. No selling mixed in.",icon:"\uD83D\uDCDA",color:"from-blue-600 to-cyan-600",bgColor:"bg-blue-900/30",borderColor:"border-blue-500"},sales:{ratio:1,description:"Sell unabashedly. \"I'm building X. Here's how to get involved.\"",icon:"\uD83D\uDCB0",color:"from-green-600 to-emerald-600",bgColor:"bg-green-900/30",borderColor:"border-green-500"},personal:{ratio:1,description:"Personal/behind-the-scenes. The real me, struggles included.",icon:"\uD83D\uDE4B",color:"from-purple-600 to-pink-600",bgColor:"bg-purple-900/30",borderColor:"border-purple-500"}},l={problem:{label:"Problem",description:"Identify the pain point",icon:"\uD83C\uDFAF"},amplify:{label:"Amplify",description:"Make the problem feel urgent",icon:"\uD83D\uDCE2"},credibility:{label:"Credibility",description:"Show why you're qualified",icon:"\uD83C\uDFC6"},educate:{label:"Educate",description:"Provide value and solutions",icon:"\uD83D\uDCD6"},request:{label:"Request",description:"Clear call to action",icon:"\uD83D\uDC49"}},d={name:"Johnnie Fields",title:"Director of Admissions at Fusion Academy (DC)",northStar:"I can't be put into a box. I'm a work in progress, pivoting into tech and data while leveraging 10+ years in education.",tone:"Expert + direct, inspiring. Process Champion energy."},p=[{value:"cold_email",label:"Cold Email",icon:"\uD83D\uDCE7"},{value:"linkedin_post",label:"LinkedIn Post",icon:"\uD83D\uDCDD"},{value:"linkedin_dm",label:"LinkedIn DM",icon:"\uD83D\uDCAC"},{value:"instagram_post",label:"Instagram Post",icon:"\uD83D\uDCF8"}];function c(){let[e,t]=(0,i.useState)([]),[o,c]=(0,i.useState)("value"),[u,h]=(0,i.useState)(!1),[x,g]=(0,i.useState)(!1),[m,f]=(0,i.useState)([]),[b,y]=(0,i.useState)("linkedin_post"),[v,w]=(0,i.useState)(""),[C,j]=(0,i.useState)(""),[k,S]=(0,i.useState)([]),[I,P]=(0,i.useState)("general"),[D,A]=(0,i.useState)(null),z=e=>{t(e),localStorage.setItem("content_pipeline_911",JSON.stringify(e))};(0,i.useMemo)(()=>{let t=e.filter(e=>"value"===e.category).length,o=e.filter(e=>"sales"===e.category).length,n=e.filter(e=>"personal"===e.category).length;return{value:t,sales:o,personal:n,total:t+o+n}},[e]);let _=t=>e.filter(e=>e.category===t),B=async()=>{g(!0);try{let e=await (0,r.SC)("/api/content-generation/generate",{method:"POST",body:JSON.stringify({user_id:"johnnie_fields",topic:v||"professional growth",context:C||"",content_type:b,category:o,pacer_elements:k.map(e=>e.charAt(0).toUpperCase()+e.slice(1)),tone:"expert_direct",audience:I})}),t=await e.json();if(console.log("API Response:",t),t?.success&&t?.options&&t.options.length>0)f(t.options);else{console.log("API returned no options, using templates");let e=T(o,b,{topic:v,context:C,pacer:k});f(e)}}catch(e){console.error("Content generation error:",e),f(T(o,b,{topic:v,context:C,pacer:k}))}g(!1)},T=(e,t,o)=>{let{topic:n,context:i,pacer:r}=o;if("value"===e){if("linkedin_post"===t)return[`🎯 ${n||"Here's what I learned this week"}:

After 10+ years in education - from AmeriCorps to managing $34M portfolios at 2U to now Fusion Academy - I've learned one thing:

There are only 3 things you can influence: People, Process, and Culture.

${i||"Working with neurodivergent students"} has reinforced this:

1️⃣ PEOPLE: Meet students where they are
2️⃣ PROCESS: Systems that flex for different learning styles
3️⃣ CULTURE: An environment where "different" is the norm

What's your experience? 👇

#Education #Neurodivergent #Leadership`,`📊 Hot take: ${n||"Most advice misses the point"}.

Teams don't perform because:
• They don't have a clear goal, OR
• They don't believe in the plan

That's it. Everything else is noise.

At Fusion Academy, we serve neurodivergent students 1:1. The "traditional" approach doesn't work for everyone.

What I've learned:
• Process Champion > Hero Ball
• Constructive dialogue > Power moves
• Temperature gauge your team

Thoughts?

#Leadership #Education #ProcessChampion`,`I used to think ${n||"success"} was about following the traditional path.

I was wrong.

After 10+ years - AmeriCorps, 2U, Catholic University, now Fusion Academy - here's what actually moves the needle:

→ Relationships first. Power moves damage trust.
→ Be the last to speak.
→ Solve problems before they become big.

I'm a work in progress. Can't be put in a box. Neither can you.

Agree or disagree? 👇`];if("cold_email"===t)return[`Subject: Quick question about ${n||"neurodivergent student support"}

Hi ${i||"there"},

I'm Johnnie Fields, Director of Admissions at Fusion Academy DC. I noticed you're working with ${n||"students who learn differently"} and wanted to reach out.

I've spent 10+ years in education - from managing $34M portfolios at 2U to now serving neurodivergent students. I'm always looking to connect with professionals who share this mission.

Would you be open to a quick conversation?

Best,
Johnnie`,`Subject: Idea for ${i||"your practice"}

Hi,

I came across your work in ${n||"education/mental health"} and had a thought.

At Fusion Academy DC, we serve neurodivergent students with 1:1 instruction. I'm building referral relationships with professionals who work with families seeking alternative education options.

Worth a 15-minute call?

Best,
Johnnie Fields
Director of Admissions, Fusion Academy`]}else if("sales"===e)return[`🚀 I'm building something.

After 10+ years in education and pivoting into tech, I'm creating ${n||"Easy Outfit"} - ${i||"a fashion app that helps you use what you have"}.

Why? I've always wanted to look good but sometimes missed the mark. This solves my own problem.

Looking for:
• Beta testers
• Feedback from people who struggle with styling
• Connections to fashion/tech folks

DM me if interested. No pitch deck, just building.

#BuildInPublic #Fashion #Tech`,`📣 Let me be direct.

I consult on enrollment management and program launches. 10+ years experience. $34M portfolios. Salesforce migrations.

If you need help with:
• Admissions process optimization
• Team coaching and development
• Pipeline management
• Program launches

Let's talk. DM me or comment below.

No fluff. Just results.

#Consulting #Education #EnrollmentManagement`];else if("personal"===e)return[`I can't be put into a box.

Son of a mechanic from St. Louis.
Fell in love with fashion in a random textile course.
10+ years in education.
Now pivoting into tech.
Neurodivergent professional helping neurodivergent students.

I'm a work in progress. And that's the point.

You're witnessing my journey - the wins, the struggles, the evolution.

Who else refuses to be defined by a single label? 👇

#WorkInProgress #CantBePutInABox #Journey`,`I used to dominate conversations.

I'd talk over people. Interrupt. Make sure my point was heard.

It made me appear intimidating. And honestly? It hurt my relationships.

So I changed.

Now I make it my business to be the LAST person to talk.

The result? More fruitful exchanges. Heavier adoption of my ideas. Better relationships.

Growth isn't comfortable. But it's worth it.

What's something you've had to unlearn? 👇`,`The InspireSTL story.

My first job out of college wasn't a job - it was a mission.

I helped found a nonprofit to prepare underprivileged youth in St. Louis. I mentored 20+ students. ACT prep. Resume workshops. Mock interviews.

Less than 20% would have made it to a 4-year university without intervention.

100% were admitted.

That's when I fell in love with coaching and mentoring. That's why I'm still in education 10+ years later.

Some things choose you.

#Education #Mentoring #Purpose`];return["Generated content will appear here..."]},R=(t,n)=>{z([{id:`content_${Date.now()}_${n}`,category:o,type:b,title:t.split("\n")[0].slice(0,50)+"...",content:t,pacer_elements:k,status:"draft",created_at:new Date().toISOString(),tags:[v].filter(Boolean)},...e]),f(e=>e.filter((e,t)=>t!==n))},E=t=>{z(e.filter(e=>e.id!==t))},W=e=>{navigator.clipboard.writeText(e)},F=e=>{k.includes(e)?S(k.filter(t=>t!==e)):S([...k,e])};return(0,n.jsxs)("main",{style:{minHeight:"100vh",backgroundColor:"#0f172a"},children:[n.jsx(s.Z,{}),(0,n.jsxs)("div",{style:{maxWidth:"1400px",margin:"0 auto",padding:"24px"},children:[(0,n.jsxs)("div",{style:{marginBottom:"24px"},children:[n.jsx("h1",{style:{fontSize:"28px",fontWeight:"bold",color:"white",marginBottom:"8px"},children:"Content Pipeline"}),n.jsx("p",{style:{color:"#9ca3af"},children:"Chris Do 911 Framework: 9 Value • 1 Sales • 1 Personal"})]}),n.jsx("div",{style:{background:"linear-gradient(to right, #1e293b, #334155)",borderRadius:"12px",padding:"16px",marginBottom:"24px",border:"1px solid #475569"},children:(0,n.jsxs)("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"start"},children:[(0,n.jsxs)("div",{children:[(0,n.jsxs)("div",{style:{display:"flex",alignItems:"center",gap:"8px",marginBottom:"4px"},children:[n.jsx("span",{style:{fontSize:"18px",fontWeight:600,color:"white"},children:d.name}),n.jsx("span",{style:{fontSize:"12px",padding:"2px 8px",backgroundColor:"rgba(59, 130, 246, 0.3)",borderRadius:"4px",color:"#93c5fd"},children:"Persona Active"})]}),n.jsx("p",{style:{fontSize:"14px",color:"#9ca3af"},children:d.title}),n.jsx("p",{style:{fontSize:"12px",color:"#6b7280",marginTop:"8px",maxWidth:"600px"},children:d.northStar})]}),n.jsx("div",{style:{textAlign:"right",fontSize:"12px",color:"#6b7280"},children:(0,n.jsxs)("div",{children:["Tone: ",d.tone]})})]})}),n.jsx("div",{style:{display:"grid",gridTemplateColumns:"repeat(3, 1fr)",gap:"16px",marginBottom:"24px"},children:["value","sales","personal"].map(e=>{let t=a[e],i=_(e).length,r=o===e;return(0,n.jsxs)("button",{onClick:()=>c(e),style:{padding:"20px",borderRadius:"12px",border:r?`2px solid ${"value"===e?"#3b82f6":"sales"===e?"#22c55e":"#a855f7"}`:"2px solid #475569",backgroundColor:r?"value"===e?"rgba(59, 130, 246, 0.1)":"sales"===e?"rgba(34, 197, 94, 0.1)":"rgba(168, 85, 247, 0.1)":"#1e293b",textAlign:"left",cursor:"pointer",transition:"all 0.2s"},children:[(0,n.jsxs)("div",{style:{display:"flex",alignItems:"center",gap:"12px",marginBottom:"8px"},children:[n.jsx("span",{style:{fontSize:"32px"},children:t.icon}),(0,n.jsxs)("div",{children:[n.jsx("div",{style:{fontSize:"24px",fontWeight:"bold",color:"white"},children:i}),(0,n.jsxs)("div",{style:{fontSize:"12px",color:"#9ca3af",textTransform:"uppercase"},children:[e," (",t.ratio,"x)"]})]})]}),n.jsx("p",{style:{fontSize:"12px",color:"#6b7280"},children:t.description})]},e)})}),n.jsx("button",{onClick:()=>h(!u),style:{width:"100%",padding:"16px",borderRadius:"12px",border:"2px dashed #475569",backgroundColor:"transparent",color:"#9ca3af",fontSize:"16px",cursor:"pointer",marginBottom:"24px"},children:u?"✕ Hide Generator":`+ Generate ${o.charAt(0).toUpperCase()+o.slice(1)} Content`}),u&&(0,n.jsxs)("div",{style:{backgroundColor:"#1e293b",borderRadius:"12px",padding:"24px",marginBottom:"24px",border:"1px solid #475569"},children:[(0,n.jsxs)("h3",{style:{fontSize:"18px",fontWeight:600,color:"white",marginBottom:"16px"},children:["Generate ",o.charAt(0).toUpperCase()+o.slice(1)," Content"]}),(0,n.jsxs)("div",{style:{marginBottom:"16px"},children:[n.jsx("label",{style:{display:"block",fontSize:"14px",color:"#9ca3af",marginBottom:"8px"},children:"Content Type"}),n.jsx("div",{style:{display:"flex",gap:"8px",flexWrap:"wrap"},children:p.map(e=>(0,n.jsxs)("button",{onClick:()=>y(e.value),style:{padding:"8px 16px",borderRadius:"8px",border:"none",backgroundColor:b===e.value?"#3b82f6":"#374151",color:"white",cursor:"pointer",fontSize:"14px"},children:[e.icon," ",e.label]},e.value))})]}),"value"===o&&(0,n.jsxs)("div",{style:{marginBottom:"16px"},children:[n.jsx("label",{style:{display:"block",fontSize:"14px",color:"#9ca3af",marginBottom:"8px"},children:"PACER Framework Elements (optional)"}),n.jsx("div",{style:{display:"flex",gap:"8px",flexWrap:"wrap"},children:Object.entries(l).map(([e,t])=>(0,n.jsxs)("button",{onClick:()=>F(e),style:{padding:"8px 12px",borderRadius:"8px",border:k.includes(e)?"2px solid #22c55e":"1px solid #475569",backgroundColor:k.includes(e)?"rgba(34, 197, 94, 0.2)":"transparent",color:"white",cursor:"pointer",fontSize:"12px"},children:[t.icon," ",t.label]},e))})]}),(0,n.jsxs)("div",{style:{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:"16px",marginBottom:"16px"},children:[(0,n.jsxs)("div",{children:[n.jsx("label",{style:{display:"block",fontSize:"14px",color:"#9ca3af",marginBottom:"8px"},children:"Topic"}),n.jsx("input",{type:"text",value:v,onChange:e=>w(e.target.value),placeholder:"e.g., neurodivergent education, AI tools",style:{width:"100%",padding:"12px",borderRadius:"8px",border:"1px solid #475569",backgroundColor:"#0f172a",color:"white",fontSize:"14px"}})]}),(0,n.jsxs)("div",{children:[n.jsx("label",{style:{display:"block",fontSize:"14px",color:"#9ca3af",marginBottom:"8px"},children:"Context"}),n.jsx("input",{type:"text",value:C,onChange:e=>j(e.target.value),placeholder:"e.g., prospect name, specific situation",style:{width:"100%",padding:"12px",borderRadius:"8px",border:"1px solid #475569",backgroundColor:"#0f172a",color:"white",fontSize:"14px"}})]}),(0,n.jsxs)("div",{children:[n.jsx("label",{style:{display:"block",fontSize:"14px",color:"#9ca3af",marginBottom:"8px"},children:"Audience"}),n.jsx("select",{value:I,onChange:e=>P(e.target.value),style:{width:"100%",padding:"12px",borderRadius:"8px",border:"1px solid #475569",backgroundColor:"#0f172a",color:"white",fontSize:"14px"},children:[{value:"general",label:"General"},{value:"education_admissions",label:"Education / Admissions"},{value:"tech_ai",label:"Tech / AI"},{value:"fashion",label:"Fashion / Style"},{value:"leadership",label:"Leadership / Management"},{value:"neurodivergent",label:"Neurodivergent Support"},{value:"entrepreneurs",label:"Entrepreneurs / Founders"}].map(e=>n.jsx("option",{value:e.value,children:e.label},e.value))})]})]}),n.jsx("button",{onClick:B,disabled:x,style:{padding:"12px 24px",borderRadius:"8px",border:"none",background:"linear-gradient(to right, #3b82f6, #8b5cf6)",color:"white",fontSize:"16px",fontWeight:600,cursor:"pointer",opacity:x?.5:1},children:x?"Generating...":"Generate Options"}),m.length>0&&(0,n.jsxs)("div",{style:{marginTop:"24px"},children:[n.jsx("h4",{style:{fontSize:"14px",color:"#9ca3af",marginBottom:"12px"},children:"Generated Options"}),n.jsx("div",{style:{display:"grid",gap:"16px"},children:m.map((e,t)=>(0,n.jsxs)("div",{style:{padding:"16px",borderRadius:"8px",backgroundColor:"#0f172a",border:"1px solid #475569"},children:[n.jsx("pre",{style:{whiteSpace:"pre-wrap",fontSize:"14px",color:"#e2e8f0",marginBottom:"12px",fontFamily:"inherit",maxHeight:"200px",overflow:"auto"},children:e}),(0,n.jsxs)("div",{style:{display:"flex",gap:"8px"},children:[n.jsx("button",{onClick:()=>R(e,t),style:{padding:"8px 16px",borderRadius:"6px",border:"none",backgroundColor:"#22c55e",color:"white",fontSize:"14px",cursor:"pointer"},children:"Save to Pipeline"}),n.jsx("button",{onClick:()=>W(e),style:{padding:"8px 16px",borderRadius:"6px",border:"1px solid #475569",backgroundColor:"transparent",color:"#9ca3af",fontSize:"14px",cursor:"pointer"},children:"Copy"})]})]},t))})]})]}),(0,n.jsxs)("div",{style:{backgroundColor:"#1e293b",borderRadius:"12px",border:"1px solid #475569",overflow:"hidden"},children:[(0,n.jsxs)("div",{style:{padding:"16px 20px",borderBottom:"1px solid #475569",display:"flex",justifyContent:"space-between",alignItems:"center"},children:[(0,n.jsxs)("h3",{style:{fontSize:"16px",fontWeight:600,color:"white"},children:[a[o].icon," ",o.charAt(0).toUpperCase()+o.slice(1)," Content"]}),(0,n.jsxs)("span",{style:{fontSize:"14px",color:"#6b7280"},children:[_(o).length," items"]})]}),0===_(o).length?(0,n.jsxs)("div",{style:{padding:"48px",textAlign:"center",color:"#6b7280"},children:["No ",o," content yet. Generate some above!"]}):n.jsx("div",{children:_(o).map(e=>(0,n.jsxs)("div",{style:{padding:"16px 20px",borderBottom:"1px solid #374151"},children:[(0,n.jsxs)("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"start"},children:[(0,n.jsxs)("div",{style:{flex:1},children:[(0,n.jsxs)("div",{style:{display:"flex",alignItems:"center",gap:"8px",marginBottom:"4px"},children:[n.jsx("span",{children:p.find(t=>t.value===e.type)?.icon}),n.jsx("span",{style:{fontSize:"14px",fontWeight:500,color:"white"},children:e.title})]}),(0,n.jsxs)("p",{style:{fontSize:"13px",color:"#9ca3af",marginBottom:"8px"},children:[e.content.slice(0,120),"..."]}),e.pacer_elements&&e.pacer_elements.length>0&&n.jsx("div",{style:{display:"flex",gap:"4px"},children:e.pacer_elements.map(e=>n.jsx("span",{style:{fontSize:"10px",padding:"2px 6px",backgroundColor:"rgba(34, 197, 94, 0.2)",color:"#86efac",borderRadius:"4px"},children:l[e]?.label},e))})]}),(0,n.jsxs)("div",{style:{display:"flex",gap:"8px"},children:[n.jsx("button",{onClick:()=>A(D===e.id?null:e.id),style:{padding:"6px 12px",borderRadius:"6px",border:"1px solid #475569",backgroundColor:"transparent",color:"#9ca3af",fontSize:"12px",cursor:"pointer"},children:D===e.id?"Hide":"View"}),n.jsx("button",{onClick:()=>W(e.content),style:{padding:"6px 12px",borderRadius:"6px",border:"1px solid #475569",backgroundColor:"transparent",color:"#9ca3af",fontSize:"12px",cursor:"pointer"},children:"Copy"}),n.jsx("button",{onClick:()=>E(e.id),style:{padding:"6px 12px",borderRadius:"6px",border:"1px solid #ef4444",backgroundColor:"transparent",color:"#ef4444",fontSize:"12px",cursor:"pointer"},children:"Delete"})]})]}),D===e.id&&n.jsx("div",{style:{marginTop:"12px",padding:"12px",backgroundColor:"#0f172a",borderRadius:"8px"},children:n.jsx("pre",{style:{whiteSpace:"pre-wrap",fontSize:"14px",color:"#e2e8f0",fontFamily:"inherit"},children:e.content})})]},e.id))})]})]})]})}},5061:(e,t,o)=>{"use strict";o.d(t,{Z:()=>s});var n=o(326),i=o(434),r=o(5047);function s(){let e=(0,r.usePathname)();return n.jsx("nav",{style:{position:"sticky",top:0,zIndex:50,backgroundColor:"#0f172a",borderBottom:"2px solid #475569",boxShadow:"0 4px 6px -1px rgba(0, 0, 0, 0.3)"},children:(0,n.jsxs)("div",{style:{maxWidth:"1200px",margin:"0 auto",padding:"0 24px",display:"flex",alignItems:"center",justifyContent:"space-between"},children:[n.jsx(i.default,{href:"/",style:{fontSize:"24px",fontWeight:"bold",color:"white",padding:"16px 0",textDecoration:"none"},children:"AI Clone"}),(0,n.jsxs)("div",{style:{display:"flex",alignItems:"center",gap:"4px"},children:[[{href:"/prospect-discovery",label:"Find Prospects"},{href:"/prospects",label:"Pipeline"},{href:"/content-pipeline",label:"Content"},{href:"/topic-intelligence",label:"Intelligence"}].map(t=>n.jsx(i.default,{href:t.href,style:{padding:"16px",fontSize:"14px",fontWeight:500,color:e===t.href?"white":"#e2e8f0",textDecoration:"none",borderBottom:e===t.href?"2px solid #3b82f6":"2px solid transparent",backgroundColor:e===t.href?"#1e293b":"transparent"},children:t.label},t.href)),n.jsx(i.default,{href:"/dashboard",style:{marginLeft:"16px",padding:"8px 20px",backgroundColor:"#2563eb",color:"white",fontWeight:600,borderRadius:"8px",textDecoration:"none",boxShadow:"0 2px 4px rgba(0,0,0,0.2)"},children:"Dashboard"})]})]})})}},8528:(e,t,o)=>{"use strict";function n(){return"https://aiclone-production-32dc.up.railway.app"}async function i(e,t={}){let o=n();if(!o)throw Error("NEXT_PUBLIC_API_URL is not configured");let i=e.startsWith("http")?e:`${o}${e.startsWith("/")?e:`/${e}`}`,r={headers:{"Content-Type":"application/json",...t.headers},...t},s=await fetch(i,r);if(!s.ok){let e=await s.text().catch(()=>s.statusText);throw Error(`API request failed: ${s.status} ${s.statusText} - ${e}`)}return s}o.d(t,{SC:()=>i,kG:()=>n})},434:(e,t,o)=>{"use strict";o.d(t,{default:()=>i.a});var n=o(9404),i=o.n(n)},5047:(e,t,o)=>{"use strict";var n=o(7389);o.o(n,"useParams")&&o.d(t,{useParams:function(){return n.useParams}}),o.o(n,"usePathname")&&o.d(t,{usePathname:function(){return n.usePathname}}),o.o(n,"useRouter")&&o.d(t,{useRouter:function(){return n.useRouter}})},4588:(e,t,o)=>{"use strict";o.r(t),o.d(t,{default:()=>n});let n=(0,o(8570).createProxy)(String.raw`/Users/johnniefields/Desktop/Cursor/aiclone/frontend/app/content-pipeline/page.tsx#default`)},1506:(e,t,o)=>{"use strict";o.r(t),o.d(t,{default:()=>r,metadata:()=>i});var n=o(9510);o(7272);let i={title:"AI Clone",description:"Find prospects, generate personalized outreach, and manage your pipeline — all in one place."};function r({children:e}){return n.jsx("html",{lang:"en",children:n.jsx("body",{children:e})})}},7272:()=>{}};var t=require("../../webpack-runtime.js");t.C(e);var o=e=>t(t.s=e),n=t.X(0,[948,471,404],()=>o(2534));module.exports=n})();