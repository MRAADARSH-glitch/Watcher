const btn = document.getElementById("toggle");
const cam = document.getElementById("cam");
const cambox = document.getElementById("cambox");
let popup = null;
let timer = null, wasBreak = false, tracking = false;

const pad = n => String(n).padStart(2, "0");
const hms = s => `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s % 3600 / 60))}:${pad(s % 60)}`;
const ms = s => `${pad(Math.floor(s / 60))}:${pad(s % 60)}`;

function speak(text) {
  try { speechSynthesis.speak(new SpeechSynthesisUtterance(text)); } catch (e) {}
}

async function poll() {
  const st = await (await fetch("/status")).json();
  if (st.error) { alert(st.error); setTracking(false, true); return; }
  if (!st.running) { if (tracking) setTracking(false, true); return; }
  document.getElementById("focus").textContent = hms(st.focus);
  document.getElementById("dist").textContent = st.distractions;
  document.getElementById("away").textContent = ms(st.away);
  document.getElementById("next").textContent = st.on_break ? "On break" : ms(st.until_break);
  document.getElementById("state").textContent =
    st.on_break ? `Break time! ${ms(st.break_left)} left` :
    st.attentive ? "Focused" : `Away for ${st.away_now}s`;
  if (st.on_break && !wasBreak) speak("Time for a break. Stand up, stretch, and rest your eyes.");
  if (!st.on_break && wasBreak) speak("Break over. Let's get back to studying.");
  wasBreak = st.on_break;
}

function setTracking(on, failed) {
  tracking = on;
  btn.textContent = on ? "Stop & save session" : "Start tracking";
  cambox.hidden = !on;
  if (!on && popup && !popup.closed) popup.close();
  cam.src = on ? "/video?" + Date.now() : "";
  if (on) timer = setInterval(poll, 1000);
  else { clearInterval(timer); document.getElementById("state").textContent = failed ? "Tracking stopped (not saved)." : "Session saved. See History."; }
}

btn.onclick = async () => {
  if (!tracking) {
    const r = await fetch("/start", { method: "POST" });
    if (r.ok) setTracking(true); else alert((await r.json()).error);
  } else {
    await fetch("/stop", { method: "POST" });
    setTracking(false);
  }
};

document.getElementById("popout").onclick = () => {
  popup = window.open("/camera", "focuscam", "width=520,height=420");
  if (popup) cambox.hidden = true;
};
