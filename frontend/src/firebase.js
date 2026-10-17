// Firebase Web Client Configuration for Ceylix AI
// Reads from Vite environment variables with graceful fallback

export const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyDw94avg-apgyvubyoXuO7sDWPnmdrNars",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "ceylix-ai.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "ceylix-ai",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "ceylix-ai.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "208400372598",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:208400372598:web:51c3a167dab2b53e012057",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-6FDQZXFS8K",
};
