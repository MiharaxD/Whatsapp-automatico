"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const labels = {nao_contatado: "Não contatado", aguardando: "Aguardando resposta", agendado: "Agendado", ligar: "Ligar", finalizado: "Finalizado"};
let state = {people: [], slots: [], settings: {wait_days: 2}};
let selectedId = null;
let activeView = "people";
let importPreview = null;
let busy = false;
let toastTimer;
let importSequence = 0;

const h = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));
const key = value => String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
const personById = id => state.people.find(person => person.id === Number(id));
const badge = status => `<span class="status status-${h(status)}">${h(labels[status])}</span>`;
const dateTime = value => value ? new Date(value) : null;
const fmtDate = (value, year = false) => dateTime(value)?.toLocaleDateString("pt-BR", {day: "2-digit", month: "2-digit", ...(year ? {year: "numeric"} : {})}) || "—";
const fmtTime = value => dateTime(value)?.toLocaleTimeString("pt-BR", {hour: "2-digit", minute: "2-digit"}) || "—";
const fmtFull = value => value ? `${fmtDate(value, true)} às ${fmtTime(value)}` : "Ainda não registrado";
const dateCell = value => value ? `<span class="date-cell">${h(fmtDate(value, true))}<small>${h(fmtTime(value))}</small></span>` : '<span class="cell-dash">—</span>';
const localToday = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};
const phoneText = digits => {
  if (digits.startsWith("55") && [12, 13].includes(digits.length)) {
    const local = digits.slice(4);
    return `(${digits.slice(2, 4)}) ${local.slice(0, -4)}-${local.slice(-4)}`;
  }
  return `+${digits}`;
};

function toast(message, error = false) {
  clearTimeout(toastTimer);
  const element = $("#toast");
  const dialog = $$("dialog[open]").at(-1);
  (dialog || document.body).append(element);
  element.textContent = message;
  element.classList.toggle("error", error);
  element.hidden = false;
  toastTimer = setTimeout(() => { element.hidden = true; }, error ? 6500 : 3800);
}

async function api(path, data) {
  let response;
  try {
    response = await fetch(path, data === undefined ? {cache: "no-store"} : {
      method: "POST", headers: {"Content-Type": "application/json", "X-Local-App": "1"}, body: JSON.stringify(data)
    });
  } catch {
    throw new Error("Não consegui acessar a agenda. Confira se a janela do programa está aberta.");
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Não foi possível concluir essa ação.");
  return result;
}

function updateOverdue() {
  const limit = Date.now() - state.settings.wait_days * 86400000;
  for (const person of state.people) person.overdue = person.status === "aguardando" && Boolean(person.last_contact) && new Date(person.last_contact).getTime() <= limit;
}

async function refresh() {
  try {
    state = await api("/api/state");
    $("#connection-error").hidden = true;
    updateOverdue();
    renderPeople(); renderAgenda(); renderCalls();
    $("#people-count").textContent = state.people.length;
    $("#calls-count").textContent = state.people.filter(person => person.status === "ligar").length;
    if ($("#person-dialog").open) {
      if (personById(selectedId)) renderDetail();
      else $("#person-dialog").close();
    }
  } catch (error) {
    $("#connection-error").hidden = false;
    throw error;
  }
}

function renderPeople() {
  const overdue = state.people.filter(person => person.overdue);
  $("#overdue-banner").hidden = !overdue.length;
  $("#overdue-title").textContent = `${overdue.length} ${overdue.length === 1 ? "pessoa sem resposta" : "pessoas sem resposta"}`;
  $("#overdue-description").textContent = `Último contato há ${state.settings.wait_days} ${state.settings.wait_days === 1 ? "dia" : "dias"} ou mais. Hora de tentar de novo.`;
  const query = key($("#search").value.trim());
  const digits = query.replace(/\D/g, "");
  const filter = $("#status-filter").value;
  const people = state.people.filter(person => {
    const matches = !query || key(person.name).includes(query) || person.phone.includes(query) ||
      (/^[\d\s()+.\-]+$/.test(query) && digits && person.phone.includes(digits));
    return matches && (filter === "all" || (filter === "overdue" ? person.overdue : person.status === filter));
  });
  $("#people-body").innerHTML = people.map(person => `<tr data-open="${person.id}" tabindex="0" aria-label="Abrir contato de ${h(person.name)}" class="${person.overdue ? "is-overdue" : ""}">
    <td><button class="name-button" data-open="${person.id}">${h(person.name)}</button></td>
    <td class="phone-cell">${h(phoneText(person.phone))}</td><td>${badge(person.status)}${person.overdue ? '<span class="overdue-note">Sem resposta</span>' : ""}</td>
    <td>${dateCell(person.last_contact)}</td><td>${dateCell(person.suggested?.starts)}</td><td>${dateCell(person.booked?.starts)}</td>
    <td class="cell-notes" title="${h(person.notes)}">${person.notes ? h(person.notes) : '<span class="cell-dash">—</span>'}</td><td class="row-arrow" aria-hidden="true">→</td></tr>`).join("");
  $("#people-empty").hidden = Boolean(state.people.length);
  $("#people-no-results").hidden = !state.people.length || Boolean(people.length);
  $("#table-count").textContent = `${people.length} de ${state.people.length} ${state.people.length === 1 ? "pessoa" : "pessoas"}`;
}

function renderAgenda() {
  const date = $("#agenda-date").value;
  const showPast = $("#agenda-past").checked;
  const slots = state.slots.filter(slot => (!date || slot.starts.startsWith(date)) && (showPast || new Date(slot.starts) > new Date()));
  const groups = new Map();
  for (const slot of slots) {
    const day = slot.starts.slice(0, 10);
    if (!groups.has(day)) groups.set(day, []);
    groups.get(day).push(slot);
  }
  $("#agenda-content").innerHTML = [...groups].map(([day, items]) => {
    const weekday = new Date(`${day}T12:00:00`).toLocaleDateString("pt-BR", {weekday: "long"});
    const available = items.filter(slot => !slot.person_id).length;
    return `<article class="agenda-card"><header><div><h3>${h(fmtDate(`${day}T12:00:00`, true))}</h3><small>${h(weekday)}</small></div><span class="agenda-count">${available} ${available === 1 ? "livre" : "livres"}</span></header>${items.map(slot => `<div class="agenda-slot ${slot.person_id ? "reserved-slot" : ""} ${new Date(slot.starts) < new Date() ? "past-slot" : ""}"><span class="time">${h(fmtTime(slot.starts))}</span><div class="agenda-slot-info">${slot.person_id ? `<button class="name-button" data-open="${slot.person_id}">${h(slot.person_name)}</button><small>Reservado</small>` : '<span class="available-label">Disponível</span>'}</div>${!slot.person_id ? `<button class="slot-delete" data-delete-slot="${slot.id}" aria-label="Excluir horário ${h(fmtFull(slot.starts))}" title="Excluir horário">×</button>` : ""}</div>`).join("")}</article>`;
  }).join("") || `<div class="empty-state"><span class="empty-symbol" aria-hidden="true">▦</span><h2>${date || state.slots.length ? "Nenhum horário neste filtro" : "Sua agenda está livre para começar"}</h2><p>Cadastre uma data e os horários disponíveis para atendimento.</p><button class="button primary" data-add-slots>Adicionar horários</button></div>`;
}

function renderCalls() {
  const people = state.people.filter(person => person.status === "ligar");
  $("#calls-body").innerHTML = people.map(person => `<tr><td><button class="name-button" data-open="${person.id}">${h(person.name)}</button></td><td class="phone-cell">${h(phoneText(person.phone))}</td><td>${dateCell(person.last_contact)}</td><td class="cell-notes" title="${h(person.notes)}">${h(person.notes || "—")}</td><td><div class="call-actions"><button class="button secondary small" data-call="call-done" data-id="${person.id}">Ligação concluída</button><button class="button secondary small" data-call="no-answer" data-id="${person.id}">Não atendeu</button><button class="button primary small" data-call="schedule" data-id="${person.id}">Agendado</button></div></td></tr>`).join("");
  $("#calls-empty").hidden = Boolean(people.length);
  $("#calls-body").closest("table").classList.add("calls-table");
}

function setView(view) {
  if (view === "settings") loadSettings();
  activeView = view;
  $$(".view").forEach(section => { section.hidden = section.id !== `view-${view}`; });
  $$(".nav-button").forEach(button => {
    button.classList.toggle("active", button.dataset.view === view);
    if (button.dataset.view === view) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (view === "agenda") renderAgenda();
}

function openPerson(id) {
  if (!personById(id)) return;
  selectedId = Number(id);
  renderDetail();
  if (!$("#person-dialog").open) $("#person-dialog").showModal();
  $("#person-dialog").scrollTop = 0;
}

function renderDetail() {
  const person = personById(selectedId);
  if (!person) return;
  const focusAction = $("#person-detail").contains(document.activeElement) ? document.activeElement?.dataset?.action : null;
  const slot = person.booked || person.suggested;
  const conflict = slot && !person.booked && Boolean(slot.person_id);
  const past = slot && new Date(slot.starts) <= new Date();
  const final = person.status === "finalizado";
  const canConfirm = slot && !person.booked && !conflict && !past && !final;
  let slotContent;
  if (slot) {
    slotContent = `<div class="slot-highlight ${person.booked ? "booked" : conflict || past ? "conflict" : ""}"><p class="slot-label">${person.booked ? "AGENDAMENTO CONFIRMADO" : conflict ? "ESSE HORÁRIO JÁ FOI RESERVADO" : past ? "ESSE HORÁRIO JÁ PASSOU" : "HORÁRIO SUGERIDO"}</p><p class="slot-date">${h(fmtDate(slot.starts, true))} <small>às ${h(fmtTime(slot.starts))}</small></p><p class="slot-help">${person.booked ? "Horário reservado para esta pessoa." : conflict || past ? "Escolha o próximo horário disponível antes de confirmar." : "A sugestão não reserva. Confirme quando a pessoa aceitar."}</p></div>`;
  } else slotContent = '<div class="no-slot">Nenhum horário sugerido ainda.<br>A agenda encontra o primeiro disponível para você.</div>';
  let actions = "";
  if (person.booked) {
    actions = `<div class="detail-actions double">${!final ? '<button class="button secondary" data-action="finalize">Finalizar atendimento</button>' : '<span class="muted">Atendimento finalizado.</span>'}<button class="button danger" data-action="cancel">Cancelar agendamento</button></div>`;
  } else if (final) {
    actions = '<p class="muted">Contato finalizado. Use Editar pessoa para reabri-lo.</p>';
  } else if (!slot) {
    actions = '<div class="detail-actions"><button class="button primary" data-action="suggest">Sugerir próximo horário</button></div>';
  } else {
    actions = `<div class="detail-actions"><button class="button primary" data-action="confirm" ${canConfirm ? "" : "disabled"}>Confirmar agendamento</button><button class="button secondary" data-action="next">${conflict || past ? "Próximo horário disponível" : "Não pode nesse horário · Próximo horário"}</button></div>`;
  }
  $("#person-detail").innerHTML = `<div class="drawer-header"><div class="dialog-heading"><div><h2 id="person-detail-title">${h(person.name)}</h2><p class="drawer-phone">${h(phoneText(person.phone))}</p></div><button class="close-button" data-close="person-dialog" aria-label="Fechar contato">×</button></div>${badge(person.status)}${person.overdue ? ' <span class="overdue-note">Sem resposta · vale tentar outro contato</span>' : ""}</div><div class="drawer-content"><div class="detail-meta"><div>Último contato<strong>${h(fmtFull(person.last_contact))}</strong></div><button class="link-button" data-edit="${person.id}">Editar pessoa</button></div>${slotContent}${actions}
    ${person.message ? `<div class="message-label"><strong>Mensagem pronta</strong><span>${person.booked ? "Confirmação" : person.message_kind === "alternative" ? "Outro horário" : "Primeiro contato"}</span></div><textarea id="prepared-message" class="message-text" rows="8" aria-label="Mensagem pronta, editável antes de copiar ou abrir WhatsApp">${h(person.message)}</textarea><div class="message-actions"><button class="button whatsapp" data-whatsapp ${conflict || past || final ? "disabled" : ""}>Enviar no WhatsApp ↗</button><button class="button secondary" data-copy ${conflict || past || final ? "disabled" : ""}>Copiar mensagem</button></div><button class="sent-button" data-action="sent" ${conflict || past || final ? "disabled" : ""}>✓ Mensagem enviada</button><p class="sent-hint">Abriu a conversa? Revise e envie no WhatsApp.<br>Depois, registre o envio aqui.</p>` : ""}
    <div class="detail-notes"><strong>OBSERVAÇÃO</strong><p>${h(person.notes || "Nenhuma observação.")}</p></div><div class="drawer-footer">${!person.booked && !final ? `<button class="link-button" data-action="flag-call" ${person.status === "ligar" ? "disabled" : ""}>${person.status === "ligar" ? "Na fila de ligações" : "Marcar para ligar"}</button>` : '<span></span>'}<button class="link-button danger" data-action="delete">Excluir pessoa</button></div></div>`;
  if (focusAction) {
    const nextFocus = $(`[data-action="${focusAction}"]:not(:disabled)`, $("#person-detail")) || $(".detail-actions button:not(:disabled)", $("#person-detail")) || $("[data-close]", $("#person-detail"));
    nextFocus?.focus({preventScroll: true});
  }
}

async function personAction(id, action, message) {
  if (busy) return;
  busy = true;
  try {
    await api(`/api/people/${id}/${action}`, {});
    await refresh();
    if (message) toast(message);
  } catch (error) { toast(error.message, true); }
  finally { busy = false; }
}

function openEditor(id) {
  const person = id ? personById(id) : null;
  const form = $("#person-form");
  form.reset();
  form.elements.id.value = person?.id || "";
  form.elements.name.value = person?.name || "";
  form.elements.phone.value = person ? `+${person.phone}` : "";
  form.elements.notes.value = person?.notes || "";
  const options = person?.booked ? ["agendado", "finalizado"] : ["nao_contatado", "aguardando", "ligar", "finalizado"];
  form.elements.status.innerHTML = options.map(status => `<option value="${status}">${labels[status]}</option>`).join("");
  form.elements.status.value = person?.status || "nao_contatado";
  $("#edit-status-label").hidden = !person;
  $("#person-form-error").hidden = true;
  $("#edit-title").textContent = person ? "Editar pessoa" : "Adicionar pessoa";
  $("#edit-dialog").showModal();
  form.elements.name.focus();
}

function openSlots() {
  const form = $("#slots-form");
  form.reset();
  form.elements.date.min = localToday();
  form.elements.date.value = $("#agenda-date").value || localToday();
  form.elements.times.value = "08:00\n08:30\n09:00\n09:30";
  $("#slots-form-error").hidden = true;
  $("#slots-dialog").showModal();
}

function loadSettings() {
  $("#wait-days").value = state.settings.wait_days;
  for (const name of ["first", "alternative", "confirmation"]) $(`#template-${name}`).value = state.settings[name] || "";
}

function inlineError(selector, error) {
  const element = $(selector);
  element.textContent = error.message;
  element.hidden = false;
}

async function saveForm(event, task, errorSelector) {
  event.preventDefault();
  if (busy) return;
  busy = true;
  const button = $("button[type=submit]", event.target);
  if (button) button.disabled = true;
  if (errorSelector) $(errorSelector).hidden = true;
  try { await task(); }
  catch (error) { if (errorSelector) inlineError(errorSelector, error); else toast(error.message, true); }
  finally { busy = false; if (button) button.disabled = false; }
}

$("#person-form").addEventListener("submit", event => saveForm(event, async () => {
  const data = Object.fromEntries(new FormData(event.target));
  const result = await api(data.id ? `/api/people/${data.id}/edit` : "/api/people", data);
  $("#edit-dialog").close();
  await refresh();
  toast(data.id ? "Pessoa atualizada." : "Pessoa adicionada.");
  if (!data.id) openPerson(result.id);
}, "#person-form-error"));

$("#slots-form").addEventListener("submit", event => saveForm(event, async () => {
  const data = Object.fromEntries(new FormData(event.target));
  data.times = data.times.split(/[\n,;]+/).map(time => time.trim()).filter(Boolean);
  const result = await api("/api/slots", data);
  $("#slots-dialog").close();
  await refresh();
  toast(`${result.added} ${result.added === 1 ? "horário adicionado" : "horários adicionados"}.${result.duplicates ? ` ${result.duplicates} repetido(s) ignorado(s).` : ""}`);
}, "#slots-form-error"));

$("#settings-form").addEventListener("submit", event => saveForm(event, async () => {
  const data = Object.fromEntries(new FormData(event.target));
  data.wait_days = Number(data.wait_days);
  await api("/api/settings", data);
  await refresh();
  toast("Configurações salvas.");
}));

function openImport() {
  importSequence++;
  importPreview = null;
  $("#import-file").value = "";
  $("#import-preview").innerHTML = "";
  $("#import-error").hidden = true;
  $("#import-confirm").disabled = true;
  $("#import-confirm").textContent = "Importar pessoas";
  $("#import-dialog").showModal();
}

$("#import-file").addEventListener("change", async event => {
  const sequence = ++importSequence;
  const file = event.target.files[0];
  importPreview = null;
  $("#import-confirm").disabled = true;
  $("#import-preview").innerHTML = "";
  $("#import-error").hidden = true;
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) return inlineError("#import-error", new Error("Use um arquivo de até 8 MB."));
  $("#import-preview").textContent = "Lendo sua planilha…";
  try {
    const content = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1]);
      reader.onerror = () => reject(new Error("Não foi possível ler esse arquivo."));
      reader.readAsDataURL(file);
    });
    const preview = await api("/api/import/preview", {filename: file.name, content});
    if (sequence !== importSequence || !$("#import-dialog").open) return;
    importPreview = preview;
    $("#import-preview").innerHTML = `<div class="import-summary"><strong>${preview.rows.length} ${preview.rows.length === 1 ? "pessoa pronta para importar" : "pessoas prontas para importar"}</strong>${preview.duplicates} duplicada(s) ignorada(s) · ${preview.error_count} linha(s) com erro</div>${preview.rows.length ? `<div class="import-preview-table"><table><thead><tr><th>Nome</th><th>Telefone</th><th>Observação</th></tr></thead><tbody>${preview.rows.slice(0, 15).map(person => `<tr><td>${h(person.name)}</td><td>${h(phoneText(person.phone))}</td><td>${h(person.notes)}</td></tr>`).join("")}</tbody></table></div><p class="import-note">Prévia de até 15 pessoas. Os contatos existentes serão preservados.</p>` : ""}${preview.errors.length ? `<div class="import-errors"><strong>Estas linhas não serão importadas:</strong><ul>${preview.errors.slice(0, 20).map(error => `<li>Linha ${error.line}: ${h(error.message)}</li>`).join("")}</ul>${preview.error_count > 20 ? `<p>Mais ${preview.error_count - 20} linha(s) com erro.</p>` : ""}</div>` : ""}`;
    $("#import-confirm").disabled = !preview.rows.length;
    $("#import-confirm").textContent = `Importar ${preview.rows.length} ${preview.rows.length === 1 ? "pessoa" : "pessoas"}`;
  } catch (error) {
    if (sequence !== importSequence) return;
    $("#import-preview").innerHTML = "";
    inlineError("#import-error", error);
  }
});

$("#import-confirm").addEventListener("click", async () => {
  if (busy || !importPreview?.rows.length) return;
  busy = true;
  $("#import-confirm").disabled = true;
  try {
    const result = await api("/api/import/commit", {rows: importPreview.rows});
    $("#import-dialog").close();
    await refresh();
    toast(`${result.added} ${result.added === 1 ? "pessoa importada" : "pessoas importadas"}.${result.duplicates ? ` ${result.duplicates} duplicada(s) ignorada(s).` : ""}`);
  } catch (error) { inlineError("#import-error", error); $("#import-confirm").disabled = false; }
  finally { busy = false; }
});

$("#person-detail").addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button || button.disabled || busy) return;
  const person = personById(selectedId);
  if (!person) return;
  if (button.hasAttribute("data-copy")) {
    const message = $("#prepared-message").value;
    try {
      await navigator.clipboard.writeText(message);
      toast("Mensagem copiada.");
    } catch {
      $("#prepared-message").focus(); $("#prepared-message").select();
      toast("Selecionei o texto. Pressione Ctrl+C para copiar.");
    }
  } else if (button.hasAttribute("data-whatsapp")) {
    const message = $("#prepared-message").value;
    window.open(`https://wa.me/${person.phone}?text=${encodeURIComponent(message)}`, "_blank", "noopener,noreferrer");
  } else if (button.dataset.action) {
    const action = button.dataset.action;
    if (action === "delete" && !confirm(`Excluir ${person.name}?${person.booked ? " O horário reservado será liberado." : ""} Essa exclusão não pode ser desfeita.`)) return;
    if (action === "cancel" && !confirm("Cancelar o agendamento e liberar esse horário?")) return;
    const messages = {suggest: "Horário sugerido. A mensagem está pronta.", next: "Próximo horário encontrado.", confirm: "Agendamento confirmado. Horário reservado.", sent: "Envio registrado.", "flag-call": "Pessoa adicionada à fila de ligações.", finalize: "Atendimento finalizado.", cancel: "Agendamento cancelado. Horário liberado.", delete: "Pessoa excluída."};
    button.disabled = true;
    await personAction(person.id, action, messages[action]);
    if (button.isConnected) button.disabled = false;
  }
});

document.addEventListener("click", async event => {
  const target = event.target.closest("button, [data-open]");
  if (!target || target.disabled) return;
  if (target.dataset.close) $("#" + target.dataset.close).close();
  else if (target.dataset.view) setView(target.dataset.view);
  else if (target.dataset.edit) openEditor(target.dataset.edit);
  else if (target.dataset.open) openPerson(target.dataset.open);
  else if (target.hasAttribute("data-add-slots")) openSlots();
  else if (target.dataset.deleteSlot && !busy) {
    const slot = state.slots.find(slot => slot.id === Number(target.dataset.deleteSlot));
    const suggested = state.people.some(person => person.suggested_slot_id === slot?.id);
    if (!confirm(`Excluir horário ${fmtFull(slot?.starts)}?${suggested ? " A sugestão das pessoas que receberam esse horário será removida." : ""}`)) return;
    busy = true;
    try { await api(`/api/slots/${target.dataset.deleteSlot}/delete`, {}); await refresh(); toast("Horário excluído."); }
    catch (error) { toast(error.message, true); }
    finally { busy = false; }
  } else if (target.dataset.call && !busy) {
    if (target.dataset.call === "schedule") {
      const person = personById(target.dataset.id);
      openPerson(target.dataset.id);
      if (!person?.suggested) await personAction(target.dataset.id, "suggest", "Confira o horário e confirme o aceite.");
    } else {
      const action = target.dataset.call;
      if (action === "call-done" && !confirm("Encerrar este contato como Finalizado? Se a pessoa aceitou um horário, use Agendado.")) return;
      await personAction(target.dataset.id, action, action === "no-answer" ? "Tentativa registrada. A pessoa continua na fila." : "Ligação concluída. Contato finalizado.");
    }
  }
});

$("#people-body").addEventListener("keydown", event => {
  if ((event.key === "Enter" || event.key === " ") && event.target.matches("tr[data-open]")) {
    event.preventDefault(); openPerson(event.target.dataset.open);
  }
});
$("#person-new").addEventListener("click", () => openEditor());
$("#empty-person-new").addEventListener("click", () => openEditor());
$("#import-open").addEventListener("click", openImport);
$("#slots-open").addEventListener("click", openSlots);
$("#search").addEventListener("input", renderPeople);
$("#status-filter").addEventListener("change", renderPeople);
$("#overdue-banner").addEventListener("click", () => { $("#status-filter").value = "overdue"; $("#search").value = ""; renderPeople(); });
$("#clear-filters").addEventListener("click", () => { $("#status-filter").value = "all"; $("#search").value = ""; renderPeople(); });
$("#agenda-date").addEventListener("change", renderAgenda);
$("#agenda-past").addEventListener("change", renderAgenda);
$("#agenda-all").addEventListener("click", () => { $("#agenda-date").value = ""; renderAgenda(); });
$("#reconnect").addEventListener("click", () => refresh().catch(error => toast(error.message, true)));
setInterval(() => {
  if (document.hidden || busy || $$("dialog[open]").length || activeView === "settings") return;
  refresh().catch(() => {});
}, 60000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && !busy && !$$("dialog[open]").length && activeView !== "settings") refresh().catch(() => {});
});
refresh().catch(error => toast(error.message, true));
