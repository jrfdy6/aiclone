/**
 * Firestore Server Client
 * 
 * Server-side Firebase Admin SDK for SSR data fetching.
 * Used by /kb routes to fetch knowledge and research data.
 */

import admin from "firebase-admin";

// Initialize Firebase Admin (singleton pattern)
if (!admin.apps.length) {
  try {
    const serviceAccount = process.env.FIREBASE_SERVICE_ACCOUNT
      ? JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT)
      : undefined;

    admin.initializeApp({
      credential: serviceAccount
        ? admin.credential.cert(serviceAccount)
        : admin.credential.applicationDefault(),
    });

    console.log("✅ Firebase Admin initialized for server-side operations");
  } catch (error) {
    console.error("❌ Failed to initialize Firebase Admin:", error);
    throw error;
  }
}

export const db = admin.firestore();
export const adminApp = admin;
