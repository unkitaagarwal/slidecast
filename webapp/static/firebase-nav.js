// firebase-nav.js — drop this script on any page to show signed-in user in nav
// Usage: <script type="module" src="/static/firebase-nav.js"></script>
// Expects a <div id="nav-user-slot"></div> somewhere in the nav.

import { initializeApp }                    from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import { getAuth, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";

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

const STYLE = `
  .sc-user-chip {
    display: flex; align-items: center; gap: 8px;
    background: rgba(255,247,232,0.07);
    border: 1px solid rgba(255,247,232,0.12);
    border-radius: 99px; padding: 5px 14px 5px 6px;
    font-family: inherit; cursor: default;
  }
  .sc-avatar {
    width: 28px; height: 28px; border-radius: 50%;
    background: #ff5c7a; display: flex; align-items: center;
    justify-content: center; font-size: 0.75rem; font-weight: 700;
    color: #fff; overflow: hidden; flex-shrink: 0;
  }
  .sc-avatar img { width: 100%; height: 100%; object-fit: cover; }
  .sc-name { font-size: 0.85rem; font-weight: 600; color: #fbf6ec; max-width: 120px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sc-plan { font-size: 0.7rem; font-weight: 700; color: #ff5c7a;
    text-transform: uppercase; letter-spacing: 0.06em; }
  .sc-logout {
    background: none; border: none; cursor: pointer; padding: 4px 8px;
    color: #aea394; font-size: 0.8rem; font-family: inherit;
    border-radius: 6px; transition: color 0.15s;
  }
  .sc-logout:hover { color: #ff5c7a; }
  .sc-signin {
    background: #ff5c7a; color: #fff; border: none; cursor: pointer;
    padding: 8px 18px; border-radius: 99px; font-family: inherit;
    font-size: 0.85rem; font-weight: 700; transition: opacity 0.15s;
  }
  .sc-signin:hover { opacity: 0.85; }
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

function renderUser(user) {
  const slot = getSlot(); if (!slot) return;
  const stored = JSON.parse(localStorage.getItem("sc_user") || "{}");
  const name   = user.displayName || stored.name || user.email.split("@")[0];
  const photo  = user.photoURL || stored.photo || "";
  const plan   = stored.plan || "basic";
  const initials = name.slice(0, 2).toUpperCase();

  slot.innerHTML = `
    <div class="sc-user-chip">
      <div class="sc-avatar">
        ${photo ? `<img src="${photo}" alt="${name}">` : initials}
      </div>
      <div>
        <div class="sc-name">${name}</div>
        <div class="sc-plan">${plan}</div>
      </div>
    </div>
    <button class="sc-logout" id="sc-logout-btn">Sign out</button>
  `;
  document.getElementById("sc-logout-btn").onclick = async () => {
    await signOut(auth);
    localStorage.removeItem("sc_user");
    renderSignedOut();
  };
}

function renderSignedOut() {
  const slot = getSlot(); if (!slot) return;
  slot.innerHTML = `<button class="sc-signin" onclick="window.location.href='/pricing'">Sign in</button>`;
}

injectStyles();
onAuthStateChanged(auth, user => {
  if (user) renderUser(user);
  else      renderSignedOut();
});
