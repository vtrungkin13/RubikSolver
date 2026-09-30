const API_BASE = "http://127.0.0.1:8000";
const $ = (selector) => document.querySelector(selector);

$("#solve").addEventListener("click", async () => {
  const button = $("#solve");
  $("#status").textContent = "Solving...";
  $("#result").classList.add("hidden");
  button.disabled = true;
  try {
    const response = await fetch(API_BASE + "/api/solve", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({scramble:$("#scramble").value, method:$("#method").value})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail?.message ?? "Solve request failed.");
    $("#summary").textContent = `Method: ${data.method} | Moves: ${data.move_count} | Metric: ${data.metric} | Verified: ${data.verified ? "YES" : "NO"}`;
    $("#solution").textContent = data.moves;
    $("#phases").replaceChildren(...data.phases.map((p) => { const s=document.createElement("section"); s.className="phase"; const h=document.createElement("h3"); h.textContent=p.name; const pre=document.createElement("pre"); pre.textContent=p.moves; s.append(h,pre); return s; }));
    $("#result").classList.remove("hidden");
    $("#status").textContent = "";
  } catch (error) { $("#status").textContent = error.message; }
  finally { button.disabled = false; }
});
