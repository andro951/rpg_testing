`use strict`;
(() => {
 const panel = document.createElement(`article`);
 const title = document.createElement(`h3`); title.textContent = `Full model coverage`;
 const body = document.createElement(`div`); panel.append(title, body);
 document.getElementById(`page-overview`).append(panel);
 async function refresh() {
  try {
   const response = await api(`/api/coverage/list`);
   body.replaceChildren();
   if (!response.batches.length) {
    body.textContent = `Successful accepted OPRO candidates automatically promote and run full coverage across configured desktop and Unity models. Perchance is included once on the eligible desktop.`;
    return;
   }
   for (const batch of response.batches) {
    const line = document.createElement(`p`);
    line.textContent = `${batch.adopted_batch && !batch.active_suite_matches ? `Frozen adopted suite · ` : ``}${batch.status}: ${batch.message} ${batch.workers.map(w => `${w.id}: ${w.status || `pending`}${w.rows ? ` (${w.rows.map(r => `${r.complete}/${r.required || `?`}`).join(`, `)})` : ``}`).join(`; `)}`;
    body.append(line);
    if (batch.status !== `completed`) {
     const resume = document.createElement(`button`);resume.textContent = `Resume coverage`;
     resume.onclick = async () => { try { await api(`/api/coverage/resume`, {id: batch.id, retry_blocked: true}); } catch(error) { showAlert(error.message); } };
     body.append(resume);
    }
   }
  } catch(error) { body.textContent = `Coverage status unavailable: ${error.message}`; }
 }
 refresh();setInterval(refresh,5000);
})();
