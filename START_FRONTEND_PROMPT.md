# Prompt to Start AI Clone Frontend

Copy and paste this prompt into Cursor when you're in the aiclone workspace:

---

**Prompt:**

```
I need to start the aiclone frontend development server on port 3002 to avoid conflicts with my other project (closetgptrenew) which runs on port 3000. 

Please:
1. Navigate to the frontend directory
2. Check if node_modules exists, and if not, run npm install
3. Start the Next.js dev server on port 3002 using: npm run dev -- -p 3002
4. Verify it's running correctly and show me the URL to visit

Make sure it's running on port 3002, not the default port 3000.
```

---

## Alternative Shorter Prompt

If you prefer a shorter version:

```
Start the aiclone frontend dev server on port 3002. Check dependencies first, then start with: npm run dev -- -p 3002
```

---

## Quick Manual Command

Or you can just run this directly in terminal:

```bash
cd frontend && npm install && npm run dev -- -p 3002
```

Then visit: **http://localhost:3002**
