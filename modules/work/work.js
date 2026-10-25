"use strict";

// Рабочие документы и персональные данные остаются на компьютере пользователя.
(() => {
  const { h } = window.Yakumo;
  const root = h("div", { class: "wk-app" });
  const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; };
  const state = { month: today().slice(0,7), tab: "overview", garage: "vehicles", fuel: "entries", data: null, loading: false,
    error: "", message: "", search: "", archived: false, book: null, sheet: "", period: "", preview: null, importing: false,
    candidates: null, candidatesLoading: false };
  const tabs = { overview: "Обзор", garage: "Гараж", employees: "Сотрудники и водители", cards: "Топливные карты", attendance: "Табель", fuel: "ГСМ", imports: "Документы", candidates: "Кандидаты Диска", history: "История" };
  const kinds = { opening: "Начальный остаток", receipt: "Поступление", writeoff: "Списание" };
  const statuses = { draft: "Черновик", closed: "Закрыт", cancelled: "Отменён", posted: "Проведено" };
  const working = new Set(["Я", "Н", "РВ", "С", "К"]);
  const n = (v, scale=1000, digits=3) => v == null ? "—" : (v/scale).toLocaleString("ru-RU", { maximumFractionDigits: digits, minimumFractionDigits: scale===100?2:0 });
  const inputNum = (v, scale=1000) => v == null ? "" : String(v/scale);
  const caption = (v) => [v.plate, v.model].filter(Boolean).join(" · ");
  const person = id => state.data.employees.find(x => x.id === id)?.name || "—";
  const car = id => { const v = state.data.vehicles.find(x => x.id === id); return v ? caption(v) : "—"; };
  const card = id => state.data.cards.find(x => x.id === id)?.number || "—";
  const dayDefault = () => state.month === today().slice(0,7) ? today() : `${state.month}-01`;
  const endOfMonth = () => { const [y,m] = state.month.split("-").map(Number); return `${state.month}-${new Date(y,m,0).getDate()}`; };
  const active = () => location.hash.replace(/^#\/?/, "") === "work";
  const button = (label, click, primary=false, disabled=false) => h("button", { class: "btn"+(primary ? " primary" : ""), type: "button", onclick: click, disabled }, label);
  const hint = s => h("p", { class: "row-hint wk-hint" }, s);
  const badge = (label, tone="") => h("span", { class: "wk-badge "+tone }, label);
  const empty = (title, detail="") => h("div", { class: "wk-empty" }, h("strong", {}, title), detail ? hint(detail) : "");
  const opts = (items, label) => items.map(x => [x.id, label(x)]);
  const employees = (drivers=false) => state.data.employees.filter(x => (!drivers || x.is_driver) && (x.active || state.archived));
  const vehicles = () => state.data.vehicles.filter(x => x.active || state.archived);
  const match = (...values) => !state.search || values.join(" ").toLocaleLowerCase().includes(state.search.toLocaleLowerCase());
  const assignmentAt = (vehicle, date) => state.data.assignments.find(x => x.vehicle_id === vehicle && x.start <= date && (!x.end || x.end >= date));
  function link(label, kind, extra={}) {
    const q = new URLSearchParams({ kind, month: state.month, ...extra });
    return h("a", { class: "btn", href: `/api/work/${kind === "backup" ? "backup" : "export"}?${q}`, download: true }, label);
  }
  function printLink(kind, id) {
    return h("a", { class: "btn", href: `/api/work/print?${new URLSearchParams({kind,month:state.month,...(id?{id}:{})})}`, target: "_blank", rel: "noopener" }, "Печать / PDF");
  }
  async function request(path, data, method) {
    const response = await fetch("/api/work"+path, data === undefined ? {} : { method: method || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    let result;
    try { result = await response.json(); } catch { throw Error("Сервер вернул неполный ответ. Обновите страницу"); }
    if (!response.ok) throw Error(result.error || `Ошибка ${response.status}`);
    return result;
  }
  let serial = 0;
  async function refresh(message="") {
    const current = ++serial;
    state.loading = true; state.error = "";
    if (message) state.message = message;
    draw();
    try {
      const data = await request(`?month=${encodeURIComponent(state.month)}`);
      if (current !== serial) return;
      state.data = data;
    } catch (e) { if (current === serial) state.error = e.message; }
    finally { if (current === serial) { state.loading = false; draw(); } }
  }
  async function action(path, data, message="Сохранено") {
    const result = await request(path, data);
    await refresh(message);
    return result;
  }
  function select(items, value, label, allowEmpty=true) {
    const el = h("select", { class: "text-input", "aria-label": label }, allowEmpty ? h("option", {value:""}, "Не выбрано") : "",
      items.map(([id,name]) => h("option", {value:id}, name)));
    el.value = value == null ? "" : String(value);
    return el;
  }
  function table(headers, rows, cls="") {
    return h("div", { class: "wk-table-wrap" }, h("table", { class: "wk-table "+cls },
      h("thead", {}, h("tr", {}, headers.map(x => h("th", { scope:"col" }, x)))),
      h("tbody", {}, rows.map(row => h("tr", {}, row.map(x => h("td", {}, x)))))));
  }
  function switcher(items, value, change) {
    return h("div", { class:"wk-switch", role:"tablist" }, Object.entries(items).map(([id,title]) =>
      h("button", {type:"button",class:value===id?"on":"",role:"tab","aria-selected":String(value===id),onclick:()=>change(id)}, title)));
  }
  function toolbar(...children) { return h("div", {class:"wk-toolbar"}, children); }
  function toggleArchive() {
    return h("label", {class:"wk-check"}, h("input", {type:"checkbox",checked:state.archived,onchange:e=>{state.archived=e.target.checked;draw();}}), "Показать архивные");
  }
  function formDialog(title, specs, save, options={}) {
    const controls = {}, ids = "wk-"+Math.random().toString(36).slice(2), localError = h("p", {class:"wk-error",role:"alert"});
    const form = h("form", {class:"wk-form"});
    const dialog = h("dialog", {class:"wk-dialog","aria-labelledby":ids}, h("div", {class:"wk-dialog-head"}, h("h2", {id:ids}, title),
      button("Закрыть",()=>dialog.close())));
    const fields = h("div", {class:"wk-fields"});
    specs.forEach((s,i) => {
      const id = ids+"-"+i;
      let input;
      if (s.items) input=select(s.items,s.value,s.label,s.empty!==false);
      else if (s.type==="textarea") input=h("textarea", {class:"text-input",rows:3,maxlength:s.maxlength||2000}, s.value||"");
      else input=h("input", {class:"text-input",type:s.type||"text",value:s.type==="checkbox"?undefined:s.value??"",checked:s.type==="checkbox"&&!!s.value,
        step:s.type==="number"?"any":undefined,min:s.type==="number"?0:undefined,max:s.max,maxlength:s.maxlength||300,autocomplete:"off"});
      input.id=id; input.name=s.key; input.required=!!s.required;
      if(s.readonly) input.readOnly=true;
      controls[s.key]=input;
      fields.append(h("div", {class:"wk-field"+(s.wide?" wide":"")+(s.type==="checkbox"?" check":"")},h("label", {for:id},s.label),input,s.hint?hint(s.hint):""));
    });
    const extra = h("div", {class:"wk-form-extra"});
    const submit=h("button", {class:"btn primary",type:"submit"},options.submit||"Сохранить");
    form.append(fields,extra,localError,toolbar(button("Отмена",()=>dialog.close()),submit));
    dialog.append(form);
    form.addEventListener("submit", async e => {
      e.preventDefault(); if(submit.disabled) return;
      submit.disabled=true;localError.textContent="";
      const data=Object.fromEntries(specs.map(s=>[s.key,s.type==="checkbox"?controls[s.key].checked:controls[s.key].value]));
      try { await save(data);dialog.close(); }
      catch(e) {localError.textContent=e.message;}
      finally {submit.disabled=false;}
    });
    dialog.addEventListener("close",()=>dialog.remove());
    document.body.append(dialog);
    if(typeof dialog.showModal==="function") dialog.showModal();else dialog.setAttribute("open","");
    if(options.hint) extra.append(hint(options.hint));
    return {dialog,controls,extra,submit};
  }
  function employeeForm(row={}, driver=false) {
    return formDialog(row.id?"Карточка сотрудника":"Новый сотрудник",[
      {key:"name",label:"Фамилия, имя, отчество",value:row.name,required:true,wide:true},
      {key:"position",label:"Должность",value:row.position}, {key:"personnel_no",label:"Табельный номер",value:row.personnel_no},
      {key:"is_driver",label:"Сотрудник — водитель",type:"checkbox",value:row.id?row.is_driver:driver},
      {key:"active",label:"Действующий сотрудник",type:"checkbox",value:row.active??true},
      {key:"note",label:"Примечание",type:"textarea",value:row.note,wide:true}
    ], d=>action("/save",{kind:"employees",data:{...d,...(row.id?{id:row.id}:{})}}));
  }
  function vehicleForm(row={}) {
    return formDialog(row.id?"Карточка автомобиля":"Новый автомобиль",[
      {key:"model",label:"Марка и модель",value:row.model,required:true,wide:true}, {key:"plate",label:"Госномер",value:row.plate},
      {key:"fuel",label:"Вид топлива",items:state.data.fuels.map(x=>[x,x]),value:row.fuel||"Бензин",empty:false},
      {key:"rate",label:"Норма, л/100 км",type:"number",value:inputNum(row.rate)},
      {key:"winter_rate",label:"Зимняя норма, л/100 км",type:"number",value:inputNum(row.winter_rate),hint:"Выбирается вручную при оформлении путевого листа."},
      {key:"tank",label:"Объём бака, л",type:"number",value:inputNum(row.tank)},
      {key:"active",label:"Автомобиль в работе",type:"checkbox",value:row.active??true},
      {key:"note",label:"Примечание",type:"textarea",value:row.note,wide:true}
    ],d=>action("/save",{kind:"vehicles",data:{...d,...(row.id?{id:row.id}:{})}}),{hint:"Начальный остаток и заправки вносятся отдельно в разделе «ГСМ»."});
  }
  function cardForm(row={}) {
    return formDialog(row.id?"Топливная карта":"Новая топливная карта",[
      {key:"number",label:"Номер карты",value:row.number,required:true,wide:true,maxlength:40,hint:"Хранится как текст: начальные нули и длинный номер сохраняются."},
      {key:"provider",label:"Поставщик / оператор",value:row.provider},
      {key:"employee_id",label:"Закреплена за водителем",items:opts(employees(true),x=>x.name),value:row.employee_id},
      {key:"active",label:"Действующая карта",type:"checkbox",value:row.active??true},
      {key:"note",label:"Примечание",type:"textarea",value:row.note,wide:true}
    ],d=>action("/save",{kind:"cards",data:{...d,...(row.id?{id:row.id}:{})}}));
  }
  function assignmentForm(row={}) {
    return formDialog(row.id?"Изменить срок закрепления":"Закрепить автомобиль за водителем",[
      {key:"employee_id",label:"Водитель",items:opts(state.data.employees.filter(x=>x.is_driver),x=>x.name),value:row.employee_id,required:true},
      {key:"vehicle_id",label:"Автомобиль",items:opts(state.data.vehicles,caption),value:row.vehicle_id,required:true},
      {key:"start",label:"С даты",type:"date",value:row.start||dayDefault(),required:true},
      {key:"end",label:"По дату включительно",type:"date",value:row.end||"",hint:"Оставьте пустым для действующего закрепления."},
      {key:"note",label:"Примечание",type:"textarea",value:row.note,wide:true}
    ],d=>action("/assignment",{...d,...(row.id?{id:row.id}:{})}),{hint:"Периоды одной машины или одного водителя не могут пересекаться. При смене сначала завершите прежнее закрепление."});
  }
  function movementForm(kind="receipt", vehicleId="") {
    const f=formDialog("Движение ГСМ",[
      {key:"kind",label:"Операция",items:Object.entries(kinds),value:kind,empty:false}, {key:"date",label:"Дата",type:"date",value:dayDefault(),required:true},
      {key:"vehicle_id",label:"Автомобиль",items:opts(vehicles(),caption),value:vehicleId,required:true,wide:true},
      {key:"employee_id",label:"Водитель",items:opts(employees(true),x=>x.name)},
      {key:"card_id",label:"Топливная карта",items:opts(state.data.cards.filter(x=>x.active),x=>x.number)},
      {key:"liters",label:"Количество, л",type:"number",required:true}, {key:"amount",label:"Сумма, руб. с копейками",type:"number"},
      {key:"product",label:"Марка топлива / продукт",value:""}, {key:"note",label:"Документ / примечание",type:"textarea",wide:true}
    ],d=>action("/movement",d,"Операция проведена"),{hint:"Поступление увеличивает остаток. Списание уменьшает его. Проведённую запись можно отменить с указанием причины."});
    const sync=()=>{const a=assignmentAt(f.controls.vehicle_id.value,f.controls.date.value);f.controls.employee_id.value=a?.employee_id||"";
      const c=state.data.vehicles.find(x=>x.id===f.controls.vehicle_id.value);if(c)f.controls.product.value=c.fuel;};
    f.controls.vehicle_id.addEventListener("change",sync);f.controls.date.addEventListener("change",sync);if(vehicleId)sync();
  }
  function cancelDocument(kind,row) {
    return formDialog("Отменить документ",[{key:"reason",label:"Причина отмены",type:"textarea",required:true,wide:true}],
      d=>action("/cancel",{kind,id:row.id,reason:d.reason},"Документ отменён, история сохранена"),{submit:"Отменить документ",hint:kind==="waybills"?"Связанное списание топлива тоже будет отменено.":"Остатки будут пересчитаны. Если отмена создаст отрицательный остаток, операция не выполнится."});
  }
  function waybillForm(row={}) {
    const v=row.data||{},date=row.start||dayDefault();
    const f=formDialog(row.id?"Путевой лист № "+row.number:"Новый путевой лист",[
      {key:"number",label:"Номер",value:row.number||`ПЛ-${date.replaceAll("-","")}-${state.data.waybills.length+1}`,required:true,wide:true},
      {key:"start",label:"Выезд",type:"date",value:date,required:true}, {key:"end",label:"Возвращение",type:"date",value:row.end||date,required:true},
      {key:"vehicle_id",label:"Автомобиль",items:opts(vehicles(),caption),value:row.vehicle_id,required:true,wide:true},
      {key:"employee_id",label:"Водитель",items:opts(employees(true),x=>x.name),value:row.employee_id,required:true},
      {key:"rate",label:"Норма, л/100 км",type:"number",value:inputNum(v.rate)},
      {key:"odo_start",label:"Одометр при выезде, км",type:"number",value:inputNum(v.odo_start),required:true},
      {key:"odo_end",label:"Одометр при возвращении, км",type:"number",value:inputNum(v.odo_end)},
      {key:"fuel_close",label:"Остаток при возвращении, л",type:"number",value:inputNum(v.fuel_close)},
      {key:"route",label:"Маршрут и задание",type:"textarea",value:v.route,wide:true},
      {key:"note",label:"Примечание",type:"textarea",value:v.note,wide:true}
    ],d=>action("/waybill",{...d,...(row.id?{id:row.id}:{})},"Черновик путевого листа сохранён"),
    {submit:"Сохранить черновик",hint:"Списание произойдёт при закрытии: начальный остаток + поступления − остаток при возвращении. Внесите заправки перед закрытием."});
    const totals=h("p",{class:"wk-calculation","aria-live":"polite"}),winter=button("Взять зимнюю норму",()=>{
      const c=state.data.vehicles.find(x=>x.id===f.controls.vehicle_id.value);if(c?.winter_rate!=null){f.controls.rate.value=inputNum(c.winter_rate);recalc();}
    });
    f.extra.prepend(totals,winter);
    let defaults=null,seq=0;
    const recalc=()=>{
      if(!defaults)return;
      const closing=f.controls.fuel_close.value,begin=defaults.fuel_open+defaults.refueled;
      totals.textContent=`До периода: ${n(defaults.fuel_open)} л. Поступило в периоде: ${n(defaults.refueled)} л.`+
        (closing!==""?` Расход: ${(begin/1000-Number(closing)).toLocaleString("ru-RU",{maximumFractionDigits:3})} л.`:"");
    };
    const sync=async(overwrite=true)=>{
      const c=f.controls,token=++seq;if(!c.vehicle_id.value||!c.start.value||!c.end.value)return;
      try{const d=await request(`/waybill/defaults?${new URLSearchParams({vehicle_id:c.vehicle_id.value,start:c.start.value,end:c.end.value})}`);
        if(token!==seq||!f.dialog.isConnected)return;defaults=d;
        if(overwrite){c.employee_id.value=d.employee_id||"";c.rate.value=inputNum(d.rate);if(!row.id||c.odo_start.value==="")c.odo_start.value=inputNum(d.odo_start);}
        recalc();
      }catch(e){totals.textContent=e.message;}
    };
    for(const key of ["vehicle_id","start","end"])f.controls[key].addEventListener("change",()=>sync());
    f.controls.fuel_close.addEventListener("input",recalc);if(row.id)sync(false);
  }
  function closeWaybill(row) {
    return formDialog("Закрыть путевой лист № "+row.number,[],()=>action("/waybill/close",{id:row.id},"Путевой лист закрыт. Расход проведён один раз"),
      {submit:"Закрыть и списать расход",hint:"Будут проверены закрепление машины, показания одометра и остаток топлива. После закрытия правки выполняются через отмену документа."});
  }
  function allocateForm(cardId="") {
    return formDialog("Распределить заправки из выписки",[
      {key:"card_id",label:"Карта",items:opts(state.data.cards,x=>x.number),value:cardId,required:true,wide:true},
      {key:"start",label:"С даты",type:"date",value:state.month+"-01",required:true}, {key:"end",label:"По дату",type:"date",value:endOfMonth(),required:true},
      {key:"vehicle_id",label:"Автомобиль",items:opts(vehicles(),caption),required:true,wide:true},
      {key:"employee_id",label:"Водитель в этот период",items:opts(employees(true),x=>x.name)}
    ],async d=>{const r=await request("/cards/allocate",d);await refresh(`Проведено поступлений: ${r.count}`);},
      {submit:"Провести поступления",hint:"Выберите фактическую машину за указанный период. Текущий владелец карты не подставляется в старые операции автоматически. Повторно проведённые заправки пропускаются."});
  }
  function attendanceForm(employeeId="",day="") {
    const f=formDialog(day?"Отметка табеля":"Заполнить период табеля",[
      {key:"employee_id",label:"Сотрудник",items:opts(employees(),x=>x.name),value:employeeId,required:true,wide:true},
      {key:"start",label:"С даты",type:"date",value:day||state.month+"-01",required:true},
      {key:"end",label:"По дату включительно",type:"date",value:day||endOfMonth(),required:true},
      {key:"code",label:"Обозначение",items:[["","Очистить отметку"],...Object.entries(state.data.codes).map(([k,v])=>[k,`${k} — ${v}`])],value:"Я",empty:false},
      {key:"hours",label:"Часы за день",type:"number",value:"8",max:24},
      {key:"weekdays_only",label:"Только понедельник — пятница",type:"checkbox",value:false,hint:"Праздничные переносы автоматически не определяются."},
      {key:"note",label:"Примечание",type:"textarea",wide:true}
    ],d=>action("/attendance",d,"Табель сохранён"));
    const existing=day?state.data.attendance.find(x=>x.employee_id===employeeId&&x.date===day):null;
    if(existing){f.controls.code.value=existing.code;f.controls.hours.value=inputNum(existing.minutes,60);f.controls.note.value=existing.note;}
    f.controls.code.addEventListener("change",()=>{if(!working.has(f.controls.code.value))f.controls.hours.value="0";});
  }
  function overview() {
    const d=state.data,pending=d.card_ops.filter(x=>!x.entry_id||d.entries.some(e=>e.id===x.entry_id&&e.status==="cancelled")).length;
    const stats=[[d.vehicles.filter(x=>x.active).length,"Автомобилей"],[d.employees.filter(x=>x.active&&x.is_driver).length,"Водителей"],
      [d.waybills.filter(x=>x.status==="draft").length,"Черновиков путевых"],[pending,"Заправок к распределению"]];
    return [h("div",{class:"wk-stats"},stats.map(([v,t])=>h("div",{class:"card wk-stat"},h("strong",{},String(v)),h("span",{},t)))),
      h("section",{class:"card wk-section"},h("h2",{},"Быстрые действия"),toolbar(button("Автомобиль",()=>vehicleForm()),button("Водитель",()=>employeeForm({},true)),
        button("Закрепить машину",()=>assignmentForm()),button("Заправка",()=>movementForm()),button("Путевой лист",()=>waybillForm(),true))),
      !d.vehicles.length?empty("Начните с гаража и сотрудников","Добавьте автомобиль и водителя, закрепите машину, затем внесите начальный остаток топлива. Примеры Excel можно загрузить в «Документы»."):"",
      h("section",{class:"card wk-section"},h("h2",{},"Топливо за месяц"),fuelReport()),
      h("section",{class:"card wk-section"},h("h2",{},"Организация"),hint([d.settings.organization,d.settings.department].filter(Boolean).join(" · ")||"Реквизиты появятся в печатных формах."),button("Заполнить реквизиты",settingsForm))];
  }
  function settingsForm() {
    const s=state.data.settings;
    return formDialog("Реквизиты для документов",[{key:"organization",label:"Организация",value:s.organization,wide:true},
      {key:"department",label:"Подразделение",value:s.department,wide:true},{key:"responsible",label:"Ответственный",value:s.responsible,wide:true}],d=>action("/settings",d));
  }
  function garage() {
    const content=state.garage==="vehicles"?[
      toolbar(button("Добавить автомобиль",()=>vehicleForm(),true),button("Закрепить за водителем",()=>assignmentForm()),toggleArchive()),
      table(["Автомобиль","Топливо","Норма, л/100 км","Остаток сейчас, л","Водитель на сегодня",""],vehicles().filter(v=>match(v.plate,v.model)).map(v=>[
        h("div",{},h("strong",{},v.plate||"Без госномера"),h("div",{class:"wk-meta"},v.model),!v.active?badge("Архив"):""),v.fuel,n(v.rate),n(state.data.balances[v.id]),
        person(assignmentAt(v.id,today())?.employee_id),toolbar(button("Карточка",()=>vehicleForm(v)),button("ГСМ",()=>movementForm("receipt",v.id))) ])),
      h("h3",{},"Закрепления и их история"),assignmentsView()
    ]:[toolbar(button("Новый путевой лист",()=>waybillForm(),true)),hint("Сначала внесите все заправки за период. Черновик не списывает топливо; закрытие создаёт одно списание."),
      table(["Номер / период","Машина и водитель","Пробег, км","Расход факт / норма, л","Состояние",""],state.data.waybills.filter(w=>match(w.number,car(w.vehicle_id),person(w.employee_id))).map(w=>[
        h("div",{},h("strong",{},w.number),h("div",{class:"wk-meta"},w.start+" — "+w.end)),h("div",{},car(w.vehicle_id),h("div",{class:"wk-meta"},w.data.driver_name)),
        n(w.data.distance),`${n(w.data.actual)} / ${n(w.data.norm)}`,badge(statuses[w.status],w.status),toolbar(w.status==="draft"?[
          button("Открыть",()=>waybillForm(w)),button("Закрыть",()=>closeWaybill(w),true)]:[],printLink("waybill",w.id),w.status!=="cancelled"?button("Отменить",()=>cancelDocument("waybills",w)):"" )]))];
    return [switcher({vehicles:"Автомобили",waybills:"Путевые листы"},state.garage,id=>{state.garage=id;draw();}),...content];
  }
  function assignmentsView() {
    return state.data.assignments.length?table(["Водитель","Автомобиль","С даты","По дату",""],state.data.assignments.filter(a=>match(person(a.employee_id),car(a.vehicle_id))).map(a=>[
      person(a.employee_id),car(a.vehicle_id),a.start,a.end||"Действует",button("Изменить срок",()=>assignmentForm(a))])):empty("Закреплений пока нет","За водителем можно закрепить одну машину на выбранный период.");
  }
  function employeesView() {
    return [toolbar(button("Добавить сотрудника",()=>employeeForm(),true),button("Добавить водителя",()=>employeeForm({},true)),button("Закрепить машину",()=>assignmentForm()),toggleArchive()),
      table(["Сотрудник","Должность / табельный №","Автомобиль на сегодня","Топливные карты",""],employees().filter(e=>match(e.name,e.position,e.personnel_no)).map(e=>{
        const a=state.data.assignments.find(a=>a.employee_id===e.id&&a.start<=today()&&(!a.end||a.end>=today()));
        return [h("div",{},h("strong",{},e.name),toolbar(e.is_driver?badge("Водитель"):badge("Сотрудник"),!e.active?badge("Архив"):"")),
          [e.position,e.personnel_no].filter(Boolean).join(" · ")||"—",a?car(a.vehicle_id):"—",state.data.cards.filter(c=>c.employee_id===e.id&&c.active).map(c=>h("div",{class:"wk-card-number"},c.number)),
          toolbar(button("Карточка",()=>employeeForm(e)),e.is_driver?button("Машина",()=>assignmentForm({employee_id:e.id})):"",button("Табель",()=>attendanceForm(e.id)))];})),
      hint("Архивный сотрудник сохраняется в старых документах. Табельные отметки и путевые листы не удаляются при изменении карточки.")];
  }
  function cardsView() {
    return [toolbar(button("Добавить карту",()=>cardForm(),true),button("Распределить заправки",()=>allocateForm()),toggleArchive()),
      table(["Номер карты","Оператор","Водитель","Операций за месяц",""],state.data.cards.filter(c=>(c.active||state.archived)&&match(c.number,c.provider,person(c.employee_id))).map(c=>[
        h("span",{class:"wk-card-number"},c.number),c.provider||"—",person(c.employee_id),String(state.data.card_ops.filter(o=>o.card_id===c.id).length),
        toolbar(button("Карточка",()=>cardForm(c)),button("Заправки",()=>allocateForm(c.id)))])),
      h("h3",{},"Операции из выписок"),hint("Заправки без распределения ещё не увеличивают остаток машины. Текущая привязка карты к водителю не меняет старые операции."),
      table(["Дата / время","Карта","Топливо / АЗС","Количество, л","Сумма, руб.","Состояние"],state.data.card_ops.filter(o=>match(card(o.card_id),o.product,o.station)).map(o=>[
        h("div",{},o.date,h("div",{class:"wk-meta"},o.time)),h("span",{class:"wk-card-number"},card(o.card_id)),h("div",{},o.product,h("div",{class:"wk-meta"},o.station)),n(o.liters),n(o.amount,100,2),
        o.entry_id?badge(state.data.entries.some(e=>e.id===o.entry_id&&e.status==="cancelled")?"Поступление отменено":"Распределена","closed"):badge("К распределению","draft")]))];
  }
  function attendanceView() {
    const d=state.data,count=Number(endOfMonth().slice(-2));
    const byDay=new Map(d.attendance.map(x=>[x.employee_id+":"+x.date,x]));
    const rows=employees().filter(e=>match(e.name,e.personnel_no)).map(e=>{
      let minutes=0,worked=0;
      const cells=Array.from({length:count},(_,i)=>{
        const date=`${state.month}-${String(i+1).padStart(2,"0")}`,x=byDay.get(e.id+":"+date);
        if(x&&working.has(x.code)){minutes+=x.minutes;if(x.minutes>0)worked++;}
        return h("button",{type:"button",class:"wk-day"+(x?" filled":""),"aria-label":`${e.name}, ${date}: ${x?x.code+", "+n(x.minutes,60,2)+" ч":"нет отметки"}`,
          onclick:()=>attendanceForm(e.id,date)},x?h("span",{},x.code):"·",x?.minutes?h("small",{},n(x.minutes,60,2)):"");
      });
      return [h("div",{},h("strong",{},e.name),h("div",{class:"wk-meta"},e.personnel_no)),...cells,String(worked),n(minutes,60,2)];
    });
    return [toolbar(button("Заполнить период",()=>attendanceForm(),true),link("CSV для Excel","attendance"),printLink("attendance"),toggleArchive()),
      hint("Нажмите на день для изменения. Пустая ячейка означает отсутствие отметки. Итоги часов считаются по Я, Н, РВ, С и К."),
      table(["Сотрудник",...Array.from({length:count},(_,i)=>String(i+1)),"Дней","Часов"],rows,"wk-timesheet"),
      h("div",{class:"wk-legend"},Object.entries(d.codes).map(([k,v])=>h("span",{},h("b",{},k)," — "+v)))];
  }
  function fuelReport() {
    return table(["Автомобиль","Топливо","Начало, л","Поступило, л","Списано, л","Конец, л","Пробег, км","Норма, л","Отклонение, л"],state.data.report.filter(r=>match(r.plate,r.model)).map(r=>[
      h("div",{},h("strong",{},r.plate||"Без номера"),h("div",{class:"wk-meta"},r.model)),r.fuel,...["opening","received","consumed","closing","distance","norm"].map(k=>n(r[k])),
      h("span",{class:r.variance>0?"wk-negative":""},n(r.variance))]));
  }
  function fuelView() {
    let content;
    if(state.fuel==="entries")content=[toolbar(button("Поступление",()=>movementForm("receipt"),true),button("Списание",()=>movementForm("writeoff")),
      button("Начальный остаток",()=>movementForm("opening")),link("CSV для Excel","entries")),
      table(["Дата","Машина","Операция","Литры","Сумма, руб.","Водитель / карта","Основание",""],state.data.entries.filter(e=>match(car(e.vehicle_id),e.note,e.product,person(e.employee_id))).map(e=>[
        e.date,car(e.vehicle_id),h("div",{},kinds[e.kind],e.status==="cancelled"?badge("Отменено"):""),n(e.liters),n(e.amount,100,2),h("div",{},person(e.employee_id),h("div",{class:"wk-meta wk-card-number"},e.card_id?card(e.card_id):"")),
        h("div",{},e.note,h("div",{class:"wk-meta"},e.product),e.reason?hint(e.reason):""),e.status==="posted"&&!e.source_key?.startsWith("waybill:")?button("Отменить",()=>cancelDocument("entries",e)):"" ]))];
    else if(state.fuel==="report")content=[toolbar(link("CSV для Excel","fuel"),printLink("fuel")),hint("Остаток = начало + поступления − списания. Пробег и норма берутся из закрытых путевых листов по месяцу возвращения. Пустая норма означает, что данных для расчёта нет."),fuelReport()];
    else content=[toolbar(link("CSV для Excel","reconciliation"),printLink("reconciliation")),hint("Это исходные месячные итоги из Excel. Они хранятся отдельно от проведённых операций и могут содержать ошибки исходника."),
      table(["Автомобиль","Начало, л","Поступило, л","Расход факт, л","Норма, л","Конец, л","Расхождение, л","Источник"],state.data.monthly_reports.filter(r=>match(car(r.vehicle_id),person(r.employee_id))).map(r=>[
        car(r.vehicle_id),...["opening","received","actual","norm","closing"].map(k=>n(r.data[k])),h("span",{class:r.data.balance_delta?"wk-negative":""},n(r.data.balance_delta)),
        sourceLink(state.data.imports.find(x=>x.id===r.import_id)?.document_id)]))];
    return [switcher({entries:"Движение",report:"Итоги месяца",reconciliation:"Сверка с Excel"},state.fuel,id=>{state.fuel=id;draw();}),...content];
  }
  function sourceLink(id) {return id?h("a",{class:"wk-link",href:"/api/work/source?id="+encodeURIComponent(id),download:true},"Скачать исходник"):"—";}
  function previewRows(p) {
    if(p.kind==="cards")return table(["Карта","Дата","Топливо","Литры","Сумма, руб."],p.records.map(r=>[r.card,r.date,r.product,n(r.liters),n(r.amount,100,2)]));
    if(p.kind==="attendance")return table(["Сотрудник","Дата","Обозначение","Часы"],p.records.map(r=>[r.name,r.date,r.code,n(r.minutes,60,2)]));
    return table(["Автомобиль","Водитель","Месяц","Начало, л","Приход, л","Расход, л","Конец, л"],p.records.map(r=>[
      [r.plate,r.model].filter(Boolean).join(" · "),r.driver,r.month,...["opening","received","actual","closing"].map(k=>n(r[k]))]));
  }
  async function upload(file) {
    if(!file)return;
    state.importing=true;state.error="";state.preview=null;state.book=null;draw();
    try{
      if(file.size>16*1024*1024)throw Error("Файл должен быть не больше 16 МБ");
      const r=await fetch("/api/work/import/upload?name="+encodeURIComponent(file.name),{method:"POST",headers:{"X-Yakumo":"1","Content-Type":"application/octet-stream"},body:file});
      const result=await r.json();if(!r.ok)throw Error(result.error||"Не удалось загрузить файл");
      state.book=result;state.sheet=result.sheets.length===1?result.sheets[0]:"";state.period="";
      state.message="Файл загружен. Выберите лист и проверьте данные перед импортом.";
    }catch(e){state.error=e.message;}finally{state.importing=false;draw();}
  }
  async function inspectBook(id) {
    try{state.book=await request("/import/book?id="+encodeURIComponent(id));state.sheet="";state.period="";state.preview=null;state.tab="imports";draw();}
    catch(e){state.error=e.message;draw();}
  }
  async function previewBook() {
    state.importing=true;state.error="";draw();
    try{state.preview=await request("/import/preview",{id:state.book.id,sheet:state.sheet,period:state.period});}
    catch(e){state.preview=null;state.error=e.message;}finally{state.importing=false;draw();}
  }
  async function commitBook() {
    if(state.importing||!state.preview)return;
    state.importing=true;state.error="";draw();
    try{const r=await request("/import/commit",{id:state.book.id,sheet:state.sheet,period:state.period});
      const p=Array.isArray(r.period)?r.period[0]:r.period;if(p)state.month=p;
      state.preview=null;await refresh(`Импортировано записей: ${r.count}. Пропущено совпадающих операций: ${r.skipped}.`);
    }catch(e){state.error=e.message;}finally{state.importing=false;draw();}
  }
  function importsView() {
    const file=h("input",{type:"file",accept:".xlsx,.xls","aria-label":"Выберите пример Excel",onchange:e=>upload(e.target.files[0])});
    const parts=[h("section",{class:"card wk-section"},h("h2",{},"Загрузить Excel"),hint("Ведомость расхода ГСМ, месячный лист машины, табель или выписка карт. До 16 МБ. Макросы и внешние ссылки не выполняются."),file)];
    if(state.book){
      const sheet=select(state.book.sheets.map(s=>[s,s]),state.sheet,"Лист книги");sheet.onchange=()=>{state.sheet=sheet.value;state.preview=null;draw();};
      const period=h("input",{class:"text-input",type:"month",value:state.period,"aria-label":"Период импорта вручную",onchange:e=>{state.period=e.target.value;state.preview=null;draw();}});
      parts.push(h("section",{class:"card wk-section"},h("h2",{},state.book.name),h("div",{class:"wk-fields"},
        h("label",{},"Лист книги",sheet),h("label",{},"Период вручную (необязательно)",period)),
        hint("Без ручного периода год и месяц берутся из содержимого листа. Название вкладки может относиться к другому году."),
        toolbar(button(state.importing?"Читаю…":"Предварительный просмотр",previewBook,true,!state.sheet||state.importing),sourceLink(state.book.id))));
    }
    if(state.preview){const p=state.preview;parts.push(h("section",{class:"card wk-section"},h("h2",{},p.title),
      hint(`Период: ${Array.isArray(p.period)?p.period.join(", "):p.period}. Найдено записей: ${p.count}. Показаны первые ${p.records.length}.`),
      ...p.errors.map(s=>h("p",{class:"wk-error"},s)),...p.warnings.map(s=>h("p",{class:"wk-notice"},s)),previewRows(p),
      toolbar(button("Импортировать выбранный лист",commitBook,true,state.importing||!!p.errors.length))));}
    parts.push(h("h3",{},"Загруженные исходники"),state.data.documents.length?table(["Документ","Размер",""],state.data.documents.map(d=>[
      d.name,`${n(d.size,1024,1)} КБ`,toolbar(button("Выбрать лист",()=>inspectBook(d.id)),sourceLink(d.id))])):empty("Документы ещё не загружены"));
    return parts;
  }
  async function loadCandidates() {
    state.candidatesLoading = true; state.error = ""; draw();
    try { state.candidates = await request("/disk-candidates"); }
    catch(e) { state.error = e.message; state.candidates = {items:[],available:false}; }
    finally { state.candidatesLoading = false; draw(); }
  }
  function candidatesView() {
    const box = state.candidates;
    if (!box) return [h("section",{class:"card wk-section"},h("h2",{},"Кандидаты из Диска"),
      hint("Yakumo извлекает машину, водителя, дату, литры и сумму из документов. Это подсказки, а не проведённые операции."),
      toolbar(button(state.candidatesLoading?"Читаю документы…":"Проверить документы",loadCandidates,true,state.candidatesLoading)))];
    const items = box.items || [];
    return [h("section",{class:"card wk-section"},h("h2",{},"Кандидаты из Диска"),
      hint(box.warning || "Каждую строку нужно сверить с исходным документом. Ничего не попадает в ГСМ или путевые листы автоматически."),
      toolbar(button(state.candidatesLoading?"Обновляю…":"Обновить кандидаты",loadCandidates,false,state.candidatesLoading)),
      items.length ? table(["Дата","Автомобиль","Водитель","Литры","Сумма, руб.","Источник","Статус"],items.map(x=>[
        x.date||"—",x.vehicle||"—",x.driver||"—",x.liters==null?"—":String(x.liters),x.amount==null?"—":String(x.amount),
        h("a",{class:"wk-link",href:"/api/disk/file?path="+encodeURIComponent(x.path),target:"_blank",rel:"noopener"},x.path.split("/").pop()),
        badge("Требует проверки")
      ])) : empty(box.available===false?"Диск пока недоступен":"Кандидатов нет",
                    box.available===false?"Откройте Диск и дождитесь индексации документов.":"Нужны документы с автомобилем и признаками ГСМ/путевого листа."))];
  }

  function historyView() {
    return [toolbar(link("Резервная копия JSON","backup")),hint("История показывает последние 60 действий. Полная история и все учётные записи входят в резервную копию. Исходные Excel-файлы скачиваются отдельно в «Документы»."),
      table(["Когда","Действие","Раздел",""],state.data.audit.map(a=>[new Date(a.at*1000).toLocaleString("ru-RU"),a.action,
        {employees:"Сотрудники",vehicles:"Автомобили",cards:"Карты",assignments:"Закрепления",entries:"ГСМ",waybills:"Путевые листы",attendance:"Табель",imports:"Импорт",settings:"Реквизиты"}[a.kind]||a.kind,
        button("Подробности",()=>{const f=formDialog("История действия",[],async()=>{}, {submit:"Закрыть"});f.extra.append(h("pre",{class:"wk-audit"},JSON.stringify(JSON.parse(a.detail),null,2)));})]))];
  }
  function draw() {
    const month=h("input",{type:"month",class:"text-input",value:state.month,"aria-label":"Месяц учёта",onchange:e=>{if(e.target.value){state.month=e.target.value;refresh();}}});
    const search=h("input",{type:"search",class:"text-input",placeholder:"Поиск в разделе",value:state.search,"aria-label":"Поиск в разделе"});
    search.addEventListener("input",()=>{const position=search.selectionStart;state.search=search.value;draw();const next=root.querySelector('input[type="search"]');next?.focus();if(next&&position!=null)next.setSelectionRange(position,position);});
    const header=h("header",{class:"wk-header"},h("div",{},h("p",{class:"wk-eyebrow"},"YAKUMO / РАБОТА"),h("h1",{},"Работа"),hint("Гараж, люди, рабочее время и топливо в одном месте.")),
      toolbar(month,button("Обновить",()=>refresh(),false,state.loading),link("Копия данных","backup")));
    const nav=h("nav",{class:"wk-nav","aria-label":"Разделы работы"},Object.entries(tabs).map(([id,title])=>h("button",{type:"button",class:state.tab===id?"on":"",
      "aria-current":state.tab===id?"page":undefined,onclick:()=>{state.tab=id;state.search="";draw();}},title)));
    let content;
    if(!state.data)content=[empty(state.loading?"Загружаю учёт…":"Учёт пока недоступен",state.error?"Попробуйте обновить страницу.":"")];
    else content=({overview,garage,employees:employeesView,cards:cardsView,attendance:attendanceView,fuel:fuelView,imports:importsView,candidates:candidatesView,history:historyView}[state.tab])();
    root.replaceChildren(header,nav,state.error?h("div",{class:"wk-error wk-banner",role:"alert"},state.error):"",
      state.message?h("div",{class:"wk-message wk-banner",role:"status"},state.message,button("Скрыть",()=>{state.message="";draw();})):"",
      state.data?.limited.length?hint("В месяце больше 2000 записей: списки сокращены. Полные данные доступны в резервной копии."):"",
      h("section",{class:"wk-content","aria-busy":String(state.loading)},state.tab!=="overview"&&state.tab!=="imports"&&state.tab!=="history"?h("div",{class:"wk-search"},search):"",content));
  }
  window.Yakumo.addPage({id:"work",title:{ru:"Работа",en:"Work"},icon:'<path d="M3 7h18v14H3zM8 7V3h8v4M3 12h18M10 12v3h4v-3"/>',render:()=>{if(!state.data&&!state.loading)queueMicrotask(()=>refresh());draw();return [root];}});
  addEventListener("hashchange",()=>{if(active())refresh();});
})();
