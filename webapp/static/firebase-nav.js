// firebase-nav.js — drop this script on any page to show signed-in user in nav
// Usage: <script type="module" src="/static/firebase-nav.js"></script>
// Expects a <div id="nav-user-slot"></div> somewhere in the nav.

import { initializeApp }                        from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import { getAuth, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";
import { getFirestore, doc, getDoc }            from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey:            "AIzaSyANRIcHZsiB-nX2NebAeh_RVbC7I_K6u84",
  authDomain:        "slidecast-75f5c.firebaseapp.com",
  projectId:         "slidecast-75f5c",
  storageBucket:     "slidecast-75f5c.firebasestorage.app",
  messagingSenderId: "829361595060",
  appId:             "1:829361595060:web:31526e2f798ee8aba6ede1",
};

const app  = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db   = getFirestore(app);

const STYLE = `
  .sc-nav-user {
    display: flex; align-items: center; gap: 16px;
  }
  .sc-nav-email {
    font-family: inherit; font-size: 0.88rem; font-weight: 500;
    color: rgba(251,246,236,0.75);
  }
  .sc-nav-plan {
    font-size: 0.72rem; font-weight: 700; color: #ff5c7a;
    text-transform: uppercase; letter-spacing: 0.08em;
    background: rgba(255,92,122,0.12);
    border: 1px solid rgba(255,92,122,0.25);
    border-radius: 99px; padding: 2px 10px;
  }
  .sc-logout {
    background: none; border: none; cursor: pointer; padding: 0;
    color: rgba(174,163,148,0.85); font-size: 0.88rem; font-weight: 600;
    font-family: inherit; transition: color 0.15s;
  }
  .sc-logout:hover { color: #fbf6ec; }
  .sc-signin {
    background: none;
    border: 1px solid rgba(255,247,232,0.18);
    cursor: pointer; padding: 7px 18px; border-radius: 99px;
    color: #fbf6ec; font-family: inherit;
    font-size: 0.88rem; font-weight: 600;
    transition: background 0.15s;
  }
  .sc-signin:hover { background: rgba(255,247,232,0.08); }
`;

function injectStyles() {
  if (document.getElementById("sc-nav-styles")) return;
  const s = document.createElement("style");
  s.id = "sc-nav-styles";
  s.textContent = STYLE;
  document.head.appendChild(s);
}

function getSlot() {
  return document.getElementById("nav-user-slot");
}

function attachLogout(slot) {
  const btn = document.getElementById("sc-logout-btn");
  if (!btn) return;
  btn.onclick = async () => {
    await signOut(auth);
    localStorage.removeItem("sc_user");
    // Hard-navigate to home so any in-flight job state, generated slides,
    // library cache, and DOM mutations from app.js fully reset. Without this,
    // the previous user's generated panel could linger after sign-out.
    window.location.href = "/";
  };
}

function renderUserSlot(email, plan) {
  const slot = getSlot(); if (!slot) return;
  slot.innerHTML = `
    <div class="sc-nav-user">
      <span class="sc-nav-email">${email}</span>
      <span class="sc-nav-plan">${plan}</span>
      <button class="sc-logout" id="sc-logout-btn">Logout</button>
    </div>
  `;
  attachLogout(slot);
}

async function renderUser(user) {
  const slot = getSlot(); if (!slot) return;

  // Show a placeholder immediately so the nav doesn't flash empty
  const cached = JSON.parse(localStorage.getItem("sc_user") || "{}");
  if (cached.plan) renderUserSlot(user.email, cached.plan);

  // Then fetch the real plan from Firestore (source of truth)
  try {
    let snap = await getDoc(doc(db, "users", user.email));
    if (!snap.exists()) snap = await getDoc(doc(db, "users", user.uid));
    let planName = "";
    if (snap.exists()) {
      const d  = snap.data();
      const active = d.plan && d.plan !== "" && d.status === "active";
      planName = active ? d.plan : "";
    }

    // Update localStorage so the rest of the app stays in sync
    localStorage.setItem("sc_user", JSON.stringify({
      name:  user.displayName || user.email.split("@")[0],
      email: user.email,
      photo: user.photoURL || "",
      plan:  planName,
    }));

    // Always show the signed-in nav (email + Logout) when a Firebase user
    // exists. Previously we'd render the "Sign in / Sign up" button when
    // planName was empty, which was wrong: it makes a fully signed-in user
    // look signed out (happened post-Stripe-checkout before the webhook had
    // landed). The "no plan" state is now handled by the gate logic on
    // protected actions — it routes the user to /pricing if they try to do
    // something gated. The nav itself should faithfully reflect auth state.
    renderUserSlot(user.email, planName || "no plan");
  } catch (e) {
    // Firestore unavailable — render the user from auth + cache so the nav
    // still shows them as signed in. Plan label falls back to cached value
    // or "no plan" if neither source has it yet.
    console.warn("firebase-nav Firestore:", e);
    renderUserSlot(user.email, cached.plan || "no plan");
  }
}

function renderSignedOut() {
  const slot = getSlot(); if (!slot) return;
  const returnTo = encodeURIComponent(window.location.pathname);
  slot.innerHTML = `<button class="sc-signin" onclick="window.location.href='/auth?redirect=${returnTo}'">Sign in / Sign up</button>`;
}

injectStyles();
onAuthStateChanged(auth, user => {
  // Expose email globally so app.js can include it in /api/generate requests
  // for Firestore generation logging.
  window._sc_email = user ? (user.email || "") : "";
  if (user) renderUser(user);
  else      renderSignedOut();
});
