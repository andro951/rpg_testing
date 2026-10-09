`use strict`;

//#region Prompt Optimization
const PromptOptimization = {
 Selected: null,
 Current: null,
 Loading: false,
 Inputs: {},
 Initialize: () => {
  titles.optimization = `Prompt Optimization`;
  const navigation = button(`Prompt Optimization`, () => {
   setPage(`optimization`);
   return Promise.all([PromptOptimization.Models(), PromptOptimization.Refresh()]);
  });
  navigation.dataset.page = `optimization`;
  document.querySelector(`nav`).append(navigation);
  const section = el(`section`, undefined, `page hidden`);
  section.id = `page-optimization`;
  $(`page-overview`).parentElement.append(section);
  section.append(el(`h2`, `Array move prompt optimization`), el(`p`, `Pass the starting case, then test the candidate on every Array move JSON Patch test and every runnable model on this host. Rankings use full repetitions and only this host’s models. Benchmark reasoning stays off.`, `muted`));
  const controls = el(`section`);
  const generatorLabel = el(`label`, `Prompt-writing model `);
  const generator = el(`select`);
  generator.id = `optimization-generator`;
  generatorLabel.append(generator);
  controls.append(generatorLabel);
  const originLabel = el(`label`, `Starting-case model `);
  const origin = el(`select`);
  origin.id = `optimization-origin-model`;
  originLabel.append(origin);
  controls.append(el(`br`), originLabel);
  const definitions = [
   [`max_attempts`, `Maximum attempts`, `number`, 20],
   [`temperature_min`, `Temperature minimum`, `number`, .5],
   [`temperature_max`, `Temperature maximum`, `number`, .9],
   [`reasoning`, `Reasoning for prompt generation`, `checkbox`, false]
  ];
  for (const [name, text, type, value] of definitions) {
   const label = el(`label`, `${text} `);
   const input = el(`input`);
   input.type = type;
   input.id = `optimization-${name}`;
   input.setAttribute(`aria-label`, text);
   if (type === `checkbox`)
    input.checked = value;
   else
    input.value = value;

   if (name.startsWith(`temperature`))
    input.step = `.05`;

   label.append(input);
   controls.append(el(`br`), label);
   PromptOptimization.Inputs[name] = input;
  }

  const scope = el(`p`, `Opening this tab scans the host's runnable models.`, `muted`);
  scope.id = `optimization-scope`;
  const actions = el(`div`, undefined, `actions`);
  actions.append(button(`Refresh host models`, PromptOptimization.Models));
  const start = button(`Start new session`, () => PromptOptimization.Run(null), `primary`);
  start.id = `optimization-start`;
  start.disabled = true;
  actions.append(start);
  actions.append(button(`Apply settings to selected session`, async () => {
   if (!PromptOptimization.Selected)
    throw new Error(`Select a session first.`);

   await api(`/api/optimization/settings`, {session_id: PromptOptimization.Selected, settings: PromptOptimization.Settings()});
   await PromptOptimization.Refresh();
  }));
  controls.append(scope, actions);
  section.append(controls, el(`h2`, `Saved sessions`));
  const sessions = el(`select`);
  sessions.id = `optimization-sessions`;
  sessions.setAttribute(`aria-label`, `Optimization session`);
  sessions.addEventListener(`change`, async () => {
   PromptOptimization.Selected = sessions.value || null;
   await PromptOptimization.Refresh();
  });
  section.append(sessions);
  const sessionActions = el(`div`, undefined, `actions`);
  sessionActions.append(button(`Continue session`, () => PromptOptimization.Run(PromptOptimization.Selected)),
   button(`Evaluate remaining on this machine`, () => PromptOptimization.Run(PromptOptimization.Selected, `evaluate_remaining`)),
   button(`Pause`, () => api(`/api/control`, {action: `pause`})),
   button(`Resume paused run`, () => api(`/api/control`, {action: `resume`})),
   button(`Stop`, () => api(`/api/control`, {action: `stop`})),
   button(`Export session`, () => {
    if (!PromptOptimization.Selected)
     throw new Error(`Select a session first.`);

    location.href = `/api/optimization/export?id=${encodeURIComponent(PromptOptimization.Selected)}`;
   }));
  section.append(sessionActions);
  const importLabel = el(`label`, `Import a session from another machine `);
  const file = el(`input`);
  file.type = `file`;
  file.accept = `.zip`;
  file.addEventListener(`change`, () => PromptOptimization.Import(file.files[0]).catch(error => showAlert(error.message)));
  importLabel.append(file);
  section.append(importLabel);
  const status = el(`p`);
  status.id = `optimization-status`;
  const ranking = el(`div`);
  ranking.id = `optimization-ranking`;
  const history = el(`div`);
  history.id = `optimization-history`;
  section.append(status, el(`h2`, `Top three — complete current-host coverage`), ranking, el(`h2`, `All attempts`), history);
  const evidence = el(`dialog`);
  evidence.id = `optimization-evidence`;
  evidence.append(el(`h2`, `Optimization evidence`), button(`Close`, () => evidence.close()));
  const content = el(`div`);
  content.id = `optimization-evidence-content`;
  evidence.append(content);
  document.body.append(evidence);
  setInterval(() => {
   if (page === `optimization`)
    PromptOptimization.Refresh().catch(error => { $(`optimization-status`).textContent = error.message; });
  }, 2000);
 },
 Models: async () => {
  const options = await api(`/api/optimization/options`);
  const select = $(`optimization-generator`);
  const previous = select.value;
  select.replaceChildren(el(`option`, `Select a prompt-writing model`));
  select.firstChild.value = ``;
  for (const model of options.models.filter(model => model.provider === `native`)) {
   const item = el(`option`, model.name || model.id);
   item.value = model.id;
   select.append(item);
  }

  const origin = $(`optimization-origin-model`);
  const previousOrigin = origin.value;
  origin.replaceChildren();
  for (const model of options.models) {
   const item = el(`option`, model.name || model.id);
   item.value = model.id;
   origin.append(item);
  }

  if (options.models.some(model => model.id === previousOrigin))
   origin.value = previousOrigin;

  select.value = options.models.some(model => model.provider === `native` && model.id === previous) ? previous : options.default_generator || ``;
  $(`optimization-scope`).textContent = `${options.simulated ? `SIMULATED · ` : ``}Host models: ${options.models.map(model => model.name || model.id).join(`, `) || `none`}. ${options.excluded.map(model => `${model.id}: ${model.reason}`).join(`; `)}`;
  $(`optimization-start`).disabled = options.simulated || !options.models.some(model => model.provider === `native`);
 },
 Run: async (id, mode = `optimize`) => {
  if (state?.busy)
   throw new Error(`Finish or stop the current operation first.`);

  let payload;
  if (id)
   payload = {session_id: id, mode};
  else {
   if (mode === `evaluate_remaining`)
    throw new Error(`Select a saved session first.`);

   payload = {generator_id: $(`optimization-generator`).value, origin_model_id: $(`optimization-origin-model`).value, settings: PromptOptimization.Settings()};
  }

  await api(`/api/optimization/run`, payload);
  await poll();
  await PromptOptimization.Refresh();
 },
 Settings: () => {
  const settings = {};
  for (const [key, input] of Object.entries(PromptOptimization.Inputs)) {
   settings[key] = input.type === `checkbox` ? input.checked : Number(input.value);
  }

  return settings;
 },
 ShowEvidence: async (session, key) => {
  const evidence = await api(`/api/optimization/evidence?id=${encodeURIComponent(session)}&key=${key}`);
  const content = $(`optimization-evidence-content`);
  content.replaceChildren();
  const pretty = value => {
   if (typeof value !== `string`)
    return JSON.stringify(value, null, 2);

   try {
    return JSON.stringify(JSON.parse(value), null, 2);
   } catch {
    return value;
   }
  };
  const messages = evidence.messages || evidence.request_messages || [];
  for (const message of messages) {
   content.append(el(`h3`, `${message.role} message`), el(`pre`, message.content));
  }

  if (evidence.text !== undefined)
   content.append(el(`h3`, `Raw output`), el(`pre`, pretty(evidence.text)));

  for (const call of evidence.calls || []) {
   content.append(el(`h3`, `${call.step} — exact request`));
   for (const message of call.request_messages || call.messages || []) {
    content.append(el(`h4`, message.role), el(`pre`, message.content));
   }

   content.append(el(`h3`, `Output`), el(`pre`, pretty(call.text)));
  }

  if (evidence.evaluation)
   content.append(el(`h3`, `Evaluator feedback`), el(`pre`, pretty(evidence.evaluation)));

  const raw = el(`details`);
  raw.append(el(`summary`, `Complete saved record`), el(`pre`, pretty(evidence)));
  content.append(raw);
  $(`optimization-evidence`).showModal();
 },
 Refresh: async () => {
  if (PromptOptimization.Loading)
   return;

  PromptOptimization.Loading = true;
  try {
   const response = await api(`/api/optimization/sessions`);
   const sessions = $(`optimization-sessions`);
   sessions.replaceChildren();
   for (const session of response.sessions.reverse()) {
    const option = el(`option`, `${session.created} · ${session.status} · ${session.generator_id}`);
    option.value = session.id;
    sessions.append(option);
   }

   if (!response.sessions.some(session => session.id === PromptOptimization.Selected))
    PromptOptimization.Selected = response.sessions[0]?.id || null;

   if (!PromptOptimization.Selected) {
    $(`optimization-status`).textContent = `No saved optimization sessions.`;
    return;
   }

   sessions.value = PromptOptimization.Selected;
   const session = await api(`/api/optimization/session?id=${PromptOptimization.Selected}`);
   if (PromptOptimization.Current?.id !== session.id) {
    for (const [key, input] of Object.entries(PromptOptimization.Inputs)) {
     if (input.type === `checkbox`)
      input.checked = session.settings[key];
     else
      input.value = session.settings[key];
    }
   }

   PromptOptimization.Current = session;
   $(`optimization-status`).textContent = `${session.status}: ${session.message} · ${session.attempts.length}/${session.settings.max_attempts} generation attempts · ${session.scope.layers.at(-1).members.length} task-type tests · ${session.cohort.models.map(model => model.id).join(`, `)}. Original baseline: ${PromptOptimization.Percentage(session.baseline)}.`;
   const ranking = $(`optimization-ranking`);
   ranking.replaceChildren();
   for (const item of session.top_three) {
    ranking.append(el(`p`, `Candidate ${item.attempt}: ${PromptOptimization.Percentage(item)}`));
    const details = el(`details`);
    details.append(el(`summary`, `Per-model and test scores`), el(`pre`, JSON.stringify(item.summary, null, 2)));
    ranking.append(details, button(`Export candidate ${item.attempt} templates`, () => PromptOptimization.ExportCandidate(item)));
   }

   if (!session.top_three.length)
    ranking.append(el(`p`, `No candidate has completed every required trial on this host.`, `muted`));

   const history = $(`optimization-history`);
   history.replaceChildren();
   for (const attempt of session.attempts) {
    const details = el(`details`);
    details.append(el(`summary`, `Candidate ${attempt.number} · ${attempt.status} · ${PromptOptimization.Percentage(attempt.score)} · ${attempt.feedback || ``}`));
    for (const [name, key] of [[`Exact generation request`, attempt.request_evidence], [`Raw generation response`, attempt.response_evidence], [`Generation error`, attempt.error_evidence]]) {
     if (key)
      details.append(button(name, () => PromptOptimization.ShowEvidence(session.id, key)));
    }

    if (attempt.candidate)
     details.append(el(`pre`, `SYSTEM_MESSAGE:\n${attempt.candidate.system}\nUSER_MESSAGE:\n${attempt.candidate.user}`));

    history.append(details);
   }

   const trials = el(`details`);
   trials.append(el(`summary`, `Trial evidence — exact prompts, outputs and evaluator feedback`));
   for (const key of session.observations) {
    trials.append(button(key.slice(0, 12), () => PromptOptimization.ShowEvidence(session.id, key)));
   }

   history.append(trials);
  } finally {
   PromptOptimization.Loading = false;
  }
 },
 Percentage: score => score?.percentage == null ? `pending` : `${score.percentage.toFixed(1)}%${score.complete ? `` : ` (incomplete)`}`,
 ExportCandidate: item => {
  const blob = new Blob([`SYSTEM_MESSAGE:\n${item.candidate.system}\nUSER_MESSAGE:\n${item.candidate.user}`], {type: `text/plain`});
  const url = URL.createObjectURL(blob);
  const link = el(`a`);
  link.href = url;
  link.download = `candidate-${item.attempt}.txt`;
  link.click();
  URL.revokeObjectURL(url);
 },
 Import: async file => {
  if (!file)
   return;

  if (file.size > 11 * 1024 * 1024)
   throw new Error(`Session archive exceeds the browser upload limit. Copy its optimization_results folder to this repository instead.`);

  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = ``;
  for (let offset = 0; offset < bytes.length; offset += 8192) {
   binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  }

  const result = await api(`/api/optimization/import`, {archive: btoa(binary)});
  PromptOptimization.Selected = result.id;
  await PromptOptimization.Refresh();
 }
};
PromptOptimization.Initialize();
//#endregion