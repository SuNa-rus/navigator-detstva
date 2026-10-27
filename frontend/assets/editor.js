"use strict";
// MVP 0.3 editorial interface: no HTML injection of user-provided text.
(() => {
  const label = {parent:"Родитель",editor:"Редактор",medic:"Медработник",admin:"Администратор"};
  const editorialRoles = ["editor","medic","admin"];
  const nav = document.querySelector(".menu");
  const button = document.createElement("button");
  button.className = "nav-link";
  button.dataset.page = "editor";
  button.textContent = "✎ Редакция";
  button.hidden = true;
  nav.append(button);
  const panel = document.createElement("section");
  panel.className = "page";
  panel.id = "page-editor";
  panel.innerHTML = `<div class="page-header"><span class="small-label">УПРАВЛЕНИЕ МАТЕРИАЛАМИ</span><h1>Редакция</h1><p id="editor-role"></p></div>
  <div class="editor-layout"><form id="editor-form" class="editor-form" hidden>
    <h2 id="editor-form-title">Новый материал</h2>
    <label>Заголовок<input name="title" required minlength="5" maxlength="160"></label>
    <label>Категория<select name="category" id="editor-category" required></select></label>
    <label>Краткое описание<textarea name="summary" required minlength="10" maxlength="500"></textarea></label>
    <label>Полный текст<textarea name="body" required minlength="20" maxlength="20000" rows="7"></textarea></label>
    <label>Время чтения, минут<input name="reading_minutes" type="number" min="1" max="120" value="3" required></label>
    <div class="editor-actions"><button class="primary-button" type="submit">Сохранить черновик</button><button type="button" id="editor-reset">Очистить</button></div>
  </form><div><h2>Материалы и статусы</h2><div id="editor-items"></div></div></div>`;
  document.querySelector("#main-content").append(panel);
  const form = document.querySelector("#editor-form");
  let editId = null;
  const get = (q) => document.querySelector(q);
  const role = () => state.user?.role;
  const canWrite = () => ["editor","admin"].includes(role());
  const ask = async (url, options={}) => api(url, options);
  async function refreshEditor(){
    if (!editorialRoles.includes(role())) return;
    get("#editor-role").textContent = `Ваша роль: ${label[role()] || role()}. Публикацию подтверждает медработник или администратор.`;
    form.hidden = !canWrite();
    get("#editor-category").replaceChildren(...state.categories.map(c=>{
      const o=document.createElement("option");o.value=c.slug;o.textContent=c.title;return o;
    }));
    const articles=await ask("/api/editor/articles");
    const wrap=get("#editor-items");wrap.replaceChildren();
    for (const a of articles){
      const card=document.createElement("div");card.className="editor-item";
      const h=document.createElement("h3");h.textContent=a.title;card.append(h);
      const meta=document.createElement("p");meta.textContent=`Статус: ${a.status} · Автор: ${a.author || "демо"}`;card.append(meta);
      if(a.review_comment){const note=document.createElement("p");note.className="review-note";note.textContent=`Замечания: ${a.review_comment}`;card.append(note);}
      const controls=document.createElement("div");controls.className="editor-actions";
      const action=(text,fn)=>{const b=document.createElement("button");b.type="button";b.textContent=text;b.addEventListener("click",fn);controls.append(b);};
      action("Просмотреть полностью",()=>{
        const modal=document.createElement("div");modal.className="editor-preview-overlay";
        const dialog=document.createElement("section");dialog.className="editor-preview-dialog";
        dialog.setAttribute("role","dialog");dialog.setAttribute("aria-modal","true");
        const heading=document.createElement("h2");heading.textContent=a.title;dialog.append(heading);
        for(const [caption,value] of [["Категория",state.categories.find(c=>c.slug===a.category)?.title||a.category],["Автор",a.author||"Демонстрационный материал"],["Статус",a.status],["Описание",a.summary],["Полный текст",a.body]]){
          const label=document.createElement("strong");label.textContent=caption;dialog.append(label);
          const text=document.createElement("p");text.textContent=value;dialog.append(text);
        }
        const close=document.createElement("button");close.type="button";close.textContent="Закрыть";
        close.addEventListener("click",()=>modal.remove());dialog.append(close);
        modal.append(dialog);modal.addEventListener("click",e=>{if(e.target===modal)modal.remove();});document.body.append(modal);
        close.focus();
      });
      if(canWrite() && (role()==="admin" || a.author_id===state.user.id && a.status==="draft")){
        action("Изменить",()=>{
          editId=a.id;for(const field of ["title","category","summary","body","reading_minutes"]) form.elements[field].value=a[field];
          get("#editor-form-title").textContent=`Редактирование #${a.id}`;form.scrollIntoView({behavior:"smooth"});
        });
      }
      if(a.status==="draft" && canWrite() && (role()==="admin" || a.author_id===state.user.id)){
        action("Отправить на проверку",()=>change(a.id,"submit"));
      }
      if(a.status==="review" && ["medic","admin"].includes(role())){
        action("Опубликовать",()=>change(a.id,"publish"));
        action("Вернуть на доработку",async()=>{
          const comment=window.prompt("Что исправить? Укажите замечание (не менее 5 символов):");
          if(comment===null)return;
          if(comment.trim().length<5){toast("Добавьте подробное замечание");return;}
          try{await ask(`/api/editor/articles/${a.id}/return`,{method:"POST",body:JSON.stringify({comment:comment.trim()})});await refreshEditor();toast("Материал возвращён");}
          catch(e){toast(e.message);}
        });
      }
      card.append(controls);wrap.append(card);
    }
  }
  async function change(id,operation){
    try{await ask(`/api/editor/articles/${id}/${operation}`,{method:"POST"});await refreshEditor();
      state.articles=await ask("/api/articles");renderArticles();toast("Статус обновлён");}
    catch(e){toast(e.message);}
  }
  form.addEventListener("submit",async e=>{
    e.preventDefault();
    const data=Object.fromEntries(new FormData(form));data.reading_minutes=Number(data.reading_minutes);
    try{await ask(editId?`/api/editor/articles/${editId}`:"/api/editor/articles",{method:editId?"PUT":"POST",body:JSON.stringify(data)});
      form.reset();editId=null;get("#editor-form-title").textContent="Новый материал";await refreshEditor();toast("Черновик сохранён");}
    catch(err){toast(err.message);}
  });
  get("#editor-reset").addEventListener("click",()=>{editId=null;form.reset();get("#editor-form-title").textContent="Новый материал";});
  button.addEventListener("click",()=>{page("editor");get("#current-section").textContent="Редакция";refreshEditor().catch(e=>toast(e.message));});
  function updateMenu(){
    const allowed=editorialRoles.includes(role());button.hidden=!allowed;
    if(!allowed && state.page==="editor")page("home");
  }
  // Integrate with existing app's state updates without rewriting it.
  const observer=new MutationObserver(updateMenu);
  observer.observe(get("#user-button"),{childList:true,characterData:true,subtree:true});
  updateMenu();
})();
