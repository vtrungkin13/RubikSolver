import { CubeView } from "./cube-view.js";

const API_BASE = "http://127.0.0.1:8000";
const $ = selector => document.querySelector(selector);
const canvas = $("#cube-canvas");
const loading = $("#cube-loading");
const previous = $("#cube-previous");
const next = $("#cube-next");
const reset = $("#cube-reset");
const stepLabel = $("#cube-step");

let view;
let solution = null;
let moveIndex = 0;
let busy = false;
let scrambleRequest = 0;
let pendingScrambleState = null;
let pendingSolution = null;

function updateControls() {
  const count = solution?.moves?.trim() ? solution.moves.trim().split(/\s+/).length : 0;
  stepLabel.textContent = `${moveIndex} / ${count}`;
  previous.disabled = busy || !solution || moveIndex === 0;
  next.disabled = busy || !solution || moveIndex >= count;
  reset.disabled = busy || !solution;
}
function tokens() {
  return solution?.moves?.trim() ? solution.moves.trim().split(/\s+/) : [];
}
function syncHighlight() {
  document.querySelectorAll(".solution-token").forEach((node, index) => {
    node.classList.toggle("solution-move-active", index === moveIndex - 1 && moveIndex > 0);
  });
}
async function runMove(token, targetIndex) {
  if (busy || !view) return;
  const activeSolution = solution;
  busy = true;
  updateControls();
  try {
    await view.animateMove(token);
    if (solution !== activeSolution) return;
    const expected = activeSolution.step_states[targetIndex];
    const visible = view.serializeVisibleState();
    if (visible !== expected) {
      view.setState(activeSolution.step_states[moveIndex]);
      throw new Error(`Cube state mismatch at move ${token}; animation stopped. Expected ${expected}; rendered ${visible}.`);
    }
    if (targetIndex === tokens().length && (!activeSolution.verified || activeSolution.final_is_solved !== true)) {
      view.setState(activeSolution.step_states[moveIndex]);
      throw new Error("The backend did not confirm a verified solved final state; the last move was not accepted.");
    }
    moveIndex = targetIndex;
    syncHighlight();
  } catch (error) {
    if (solution === activeSolution) {
      loading.textContent = error.message;
      loading.classList.add("cube-error");
    }
  } finally {
    busy = false;
    if (pendingScrambleState) {
      view.setState(pendingScrambleState);
      pendingScrambleState = null;
    } else if (pendingSolution) {
      applySolution(pendingSolution);
      pendingSolution = null;
    }
    updateControls();
  }
}

next.addEventListener("click", () => {
  const move = tokens()[moveIndex];
  if (move) runMove(move, moveIndex + 1);
});
previous.addEventListener("click", async () => {
  if (busy || moveIndex <= 0) return;
  const move = tokens()[moveIndex - 1];
  const inverse = move.endsWith("2") ? move : move.endsWith("'") ? move[0] : `${move}'`;
  await runMove(inverse, moveIndex - 1);
});
reset.addEventListener("click", () => {
  if (busy || !solution) return;
  view.setState(solution.initial_state);
  moveIndex = 0;
  syncHighlight();
  updateControls();
});

function applySolution(data) {
  solution = data;
  moveIndex = 0;
  if (view && data.initial_state) view.setState(data.initial_state);
  loading.classList.remove("cube-error");
  loading.textContent = "";
  updateControls();
  syncHighlight();
}
document.addEventListener("rubik:solution", event => {
  if (busy) {
    pendingSolution = event.detail;
    return;
  }
  applySolution(event.detail);
});
document.addEventListener("rubik:scramble", async event => {
  const requestId = ++scrambleRequest;
  const scramble = event.detail;
  pendingSolution = null;
  if (solution) {
    solution = null;
    moveIndex = 0;
    updateControls();
  }
  try {
    const response = await fetch(`${API_BASE}/api/cube/state`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scramble })
    });
    const data = await response.json();
    if (requestId !== scrambleRequest) return;
    if (!response.ok) throw new Error(data.detail?.message || "Invalid scramble.");
    if (view && busy) pendingScrambleState = data.stickers;
    else if (view) view.setState(data.stickers);
    loading.classList.remove("cube-error");
    loading.textContent = "";
  } catch (error) {
    if (requestId === scrambleRequest) {
      loading.textContent = error.message;
      loading.classList.add("cube-error");
    }
  }
});

try {
  view = new CubeView(canvas);
  const solved = await fetch(`${API_BASE}/api/cube/state`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scramble: "" })
  }).then(response => response.json());
  view.setState(solved.stickers);
  loading.textContent = "";
  updateControls();
} catch (error) {
  loading.textContent = `3D cube unavailable: ${error.message}`;
  loading.classList.add("cube-error");
}
