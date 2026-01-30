/**
 * Firestore Server Client
 * 
 * Server-side Firebase Admin SDK for SSR data fetching.
 * Used by /kb routes to fetch knowledge and research data.
 */

import admin from "firebase-admin";

let _db: admin.firestore.Firestore | null = null;
let _initialized = false;

function initializeFirebase() {
  if (_initialized) {
    return;
  }

  if (!admin.apps.length) {
    try {
      const serviceAccount = process.env.FIREBASE_SERVICE_ACCOUNT
        ? JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT)
        : undefined;

      if (!serviceAccount) {
        console.log("⚠️ FIREBASE_SERVICE_ACCOUNT not set - Firebase Admin not initialized");
        _initialized = true;
        return;
      }

      admin.initializeApp({
        credential: admin.credential.cert(serviceAccount),
      });

      console.log("✅ Firebase Admin initialized for server-side operations");
      _db = admin.firestore();
    } catch (error) {
      console.error("❌ Failed to initialize Firebase Admin:", error);
      throw error;
    }
  } else {
    _db = admin.firestore();
  }

  _initialized = true;
}

export function getDb(): admin.firestore.Firestore {
  if (!_db) {
    initializeFirebase();
    if (!_db) {
      throw new Error("Firebase Admin is not initialized. Set FIREBASE_SERVICE_ACCOUNT environment variable.");
    }
  }
  return _db;
}

// For backward compatibility
export const db = new Proxy({} as admin.firestore.Firestore, {
  get(target, prop) {
    return getDb()[prop as keyof admin.firestore.Firestore];
  }
});

export const adminApp = admin;
