/**
 * Firestore Server Client
 * 
 * Server-side Firebase Admin SDK for SSR data fetching.
 * Used by /kb routes to fetch knowledge and research data.
 */

import { cert, getApps, initializeApp } from 'firebase-admin/app';
import { type Firestore, getFirestore } from 'firebase-admin/firestore';

let _db: Firestore | null = null;
let _initialized = false;

function initializeFirebase() {
  if (_initialized) {
    return;
  }

  const apps = getApps();
  if (!apps.length) {
    try {
      const serviceAccount = process.env.FIREBASE_SERVICE_ACCOUNT
        ? JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT)
        : undefined;

      if (!serviceAccount) {
        console.log("⚠️ FIREBASE_SERVICE_ACCOUNT not set - Firebase Admin not initialized");
        _initialized = true;
        return;
      }

      const app = initializeApp({
        credential: cert(serviceAccount),
      });

      console.log("✅ Firebase Admin initialized for server-side operations");
      _db = getFirestore(app);
    } catch (error) {
      console.error("❌ Failed to initialize Firebase Admin:", error);
      throw error;
    }
  } else {
    _db = getFirestore(apps[0]);
  }

  _initialized = true;
}

export function getDb(): Firestore {
  if (!_db) {
    initializeFirebase();
    if (!_db) {
      throw new Error("Firebase Admin is not initialized. Set FIREBASE_SERVICE_ACCOUNT environment variable.");
    }
  }
  return _db;
}

// For backward compatibility
export const db = new Proxy({} as Firestore, {
  get(target, prop) {
    return getDb()[prop as keyof Firestore];
  }
});

// Compatibility surface for any server-only caller that still expects the old
// namespace shape. The implementation uses Firebase Admin's modular API.
export const adminApp = {
  get apps() {
    return getApps();
  },
  initializeApp,
  credential: { cert },
  firestore: getFirestore,
};
