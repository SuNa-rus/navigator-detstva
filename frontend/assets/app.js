"use strict";

const state = {page: "home", articles: [], categories: [], stages: [], user: null, completed: [], category: "", search: "", mode: "login"};
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Проверьте введённые данные";
    throw new Error(detail);
  }
  return data;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { element.hidden = true; }, 3200);
}

function page(name) {
  state.page = name;
  $$(".page").forEach(el => el.classList.toggle("active", el.id === `page-${name}`));
  $$(".nav-link").forEach(el => el.classList.toggle("active", el.dataset.page === name));
  $("#current-section").textContent = {home:"Главная",library:"Школа родителей",route:"Маршрут ребёнка"}[name];
  window.scrollTo({top:0,behavior:"smooth"});
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function renderCategories() {
  const wrap = $("#category-chips");
  wrap.replaceChildren();
  [{slug:"",title:"Все материалы"}, ...state.categories].forEach(category => {
    const button = node("button", `chip ${state.category === category.slug ? "active" : ""}`, category.title);
    button.type = "button";
    button.addEventListener("click", () => {state.category = category.slug; renderCategories(); renderArticles();});
    wrap.append(button);
  });
}

function renderArticles() {
  const wrap = $("#article-grid");
  wrap.replaceChildren();
  const search = state.search.trim().toLocaleLowerCase("ru");
  const filtered = state.articles.filter(article =>
    (!state.category || state.category === article.category) &&
    (!search || `${article.title} ${article.summary}`.toLocaleLowerCase("ru").includes(search))
  );
  $("#article-count").textContent = filtered.length;
  $("#articles-empty").hidden = filtered.length !== 0;
  filtered.forEach(article => {
    const card = node("button", "article-card");
    card.type = "button";
    card.append(node("span", "article-category", article.category_title));
    card.append(node("h3", "", article.title));
    card.append(node("p", "", article.summary));
    const bottom = node("div", "article-bottom");
    bottom.append(node("span", "", `◷ ${article.reading_minutes} мин чтения`));
    bottom.append(node("b", "", "Читать →"));
    card.append(bottom);
    card.addEventListener("click", () => showArticle(article));
    wrap.append(card);
  });
}

function showArticle(article) {
  $("#article-category").textContent = article.category_title;
  $("#article-title").textContent = article.title;
  $("#article-read").textContent = `${article.reading_minutes} мин чтения`;
  $("#article-body").textContent = article.body;
  $("#article-modal").hidden = false;
  $(".article-modal-card .close-modal").focus();
}

function renderUser() {
  $("#user-button").textContent = state.user ? `◉ ${state.user.username}` : "Войти / Регистрация";
  $("#progress-info").textContent = state.user ? "Ваши отметки сохраняются в учебной учётной записи." : "Войдите, чтобы сохранять отметки между посещениями.";
  renderProgress();
}

function renderProgress() {
  const total = state.stages.length;
  const done = state.completed.length;
  const percent = total ? Math.round(done / total * 100) : 0;
  $("#progress-heading").textContent = `${done} из ${total} разделов`;
  $("#progress-percent").textContent = `${percent}%`;
  $("#progress-fill").style.width = `${percent}%`;
  $("#progress-ring").style.setProperty("--pct", `${percent}%`);
  const wrap = $("#stage-list");
  wrap.replaceChildren();
  state.stages.forEach(stage => {
    const done = state.completed.includes(stage.id);
    const card = node("div", "stage");
    card.append(node("div", "stage-number", String(stage.id).padStart(2,"0")));
    const info = node("div", "stage-info");
    const title = node("h3", "", stage.title);
    title.append(node("span", "", stage.age));
    info.append(title);
    info.append(node("p", "", stage.description));
    card.append(info);
    const action = node("button", `stage-button ${done ? "done" : ""}`, done ? "✓ Просмотрено" : "Отметить просмотр");
    action.type = "button";
    action.addEventListener("click", () => toggleProgress(stage.id, !done));
    card.append(action);
    wrap.append(card);
  });
}

async function toggleProgress(stageId, completed) {
  if (!state.user) { openAuth(); toast("Чтобы сохранять отметки, создайте учебную учётную запись"); return; }
  try {
    await api(`/api/progress/${stageId}`, {method:"PUT",body:JSON.stringify({completed})});
    state.completed = (await api("/api/progress")).completed;
    renderProgress();
    toast(completed ? "Раздел отмечен как просмотренный" : "Отметка снята");
  } catch (error) {toast(error.message);}
}

function openAuth(mode = "login") {
  state.mode = mode;
  $("#auth-error").hidden = true;
  $("#auth-form").reset();
  renderAuthMode();
  $("#auth-modal").hidden = false;
  $("#auth-username").focus();
}

function renderAuthMode() {
  $("#login-tab").classList.toggle("selected", state.mode === "login");
  $("#register-tab").classList.toggle("selected", state.mode === "register");
  $("#auth-title").textContent = state.mode === "login" ? "С возвращением!" : "Создать учётную запись";
  $("#auth-submit").textContent = state.mode === "login" ? "Войти" : "Зарегистрироваться";
  $("#auth-password").autocomplete = state.mode === "login" ? "current-password" : "new-password";
  $("#auth-error").hidden = true;
}

async function submitAuth(event) {
  event.preventDefault();
  $("#auth-error").hidden = true;
  const button = $("#auth-submit");
  button.disabled = true;
  try {
    const result = await api(`/api/${state.mode}`, {method:"POST",body:JSON.stringify({
      username: $("#auth-username").value, password: $("#auth-password").value,
    })});
    state.user = result.user;
    state.completed = (await api("/api/progress")).completed;
    $("#auth-modal").hidden = true;
    renderUser();
    toast(state.mode === "login" ? "Вы вошли в учётную запись" : "Учебная учётная запись создана");
  } catch (error) {
    $("#auth-error").textContent = error.message;
    $("#auth-error").hidden = false;
  } finally {button.disabled = false;}
}

async function accountAction() {
  if (!state.user) {openAuth(); return;}
  if (confirm(`Вы вошли как ${state.user.username}. Выйти из учётной записи?`)) {
    try {await api("/api/logout",{method:"POST"});state.user=null;state.completed=[];renderUser();toast("Вы вышли из аккаунта");}
    catch (error) {toast(error.message);}
  }
}

async function start() {
  $$("[data-page]").forEach(button => button.addEventListener("click", () => page(button.dataset.page)));
  $$("[data-close]").forEach(button => button.addEventListener("click", () => {$("#" + button.dataset.close + "-modal").hidden = true;}));
  document.addEventListener("keydown", event => {if(event.key === "Escape") $$(".modal").forEach(el => el.hidden = true);});
  $("#user-button").addEventListener("click", accountAction);
  $("#home-account").addEventListener("click", accountAction);
  $("#login-tab").addEventListener("click", () => {state.mode="login";renderAuthMode();});
  $("#register-tab").addEventListener("click", () => {state.mode="register";renderAuthMode();});
  $("#auth-form").addEventListener("submit", submitAuth);
  $("#article-search").addEventListener("input", event => {state.search=event.target.value;renderArticles();});
  try {
    const [categories, articles, stages, auth] = await Promise.all([
      api("/api/categories"),api("/api/articles"),api("/api/stages"),api("/api/me"),
    ]);
    state.categories=categories;state.articles=articles;state.stages=stages;state.user=auth.user;
    if (state.user) state.completed=(await api("/api/progress")).completed;
    renderCategories();renderArticles();renderUser();
  } catch (error) {toast("Не удалось загрузить данные: " + error.message);}
}

start();