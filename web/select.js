// Keep the existing select values and change handlers as the form's data source.
const customSelects=[];
let openSelect=null;
function syncCustomSelects(){customSelects.forEach(control=>control.sync())}
function enhanceSelect(select){
 const wrapper=el('div',undefined,'custom-select');
 select.before(wrapper);wrapper.append(select);select.classList.add('select-source');select.tabIndex=-1;
 const trigger=el('button',undefined,'select-trigger');trigger.type='button';
 const caption=el('span',undefined,'select-caption'),chevron=el('span','', 'select-chevron');chevron.setAttribute('aria-hidden','true');
 trigger.append(caption,chevron);trigger.id=select.id+'-trigger';trigger.setAttribute('role','combobox');trigger.setAttribute('aria-haspopup','listbox');trigger.setAttribute('aria-expanded','false');
 const label=select.getAttribute('aria-label')||select.closest('label')?.firstChild?.textContent.trim()||'选择';
 trigger.setAttribute('aria-label',label);
 const menu=el('div',undefined,'select-menu');menu.id=select.id+'-options';menu.setAttribute('role','listbox');menu.setAttribute('aria-label',label);menu.hidden=true;
 trigger.setAttribute('aria-controls',menu.id);wrapper.append(trigger,menu);
 let active=-1,items=[];
 function close(){menu.hidden=true;trigger.setAttribute('aria-expanded','false');trigger.removeAttribute('aria-activedescendant');if(openSelect===control)openSelect=null}
 function focusOption(index){
  active=index;items.forEach((item,i)=>item.classList.toggle('is-active',i===index));
  if(items[index]){trigger.setAttribute('aria-activedescendant',items[index].id);items[index].scrollIntoView({block:'nearest'})}
 }
 function sync(){
  wrapper.hidden=select.hidden;trigger.disabled=select.disabled;
  caption.textContent=select.selectedOptions[0]?.textContent||'请选择';
  if(!menu.hidden)renderOptions();
 }
 function choose(index){
  if(!select.options[index]||select.options[index].disabled)return;
  select.selectedIndex=index;close();caption.textContent=select.options[index].textContent;
  select.dispatchEvent(new Event('change',{bubbles:true}));trigger.focus();
 }
 function renderOptions(){
  items=[...select.options].map((option,i)=>{
   const item=el('div',option.textContent,'select-option');item.id=select.id+'-option-'+i;
   item.setAttribute('role','option');item.setAttribute('aria-selected',String(option.selected));item.setAttribute('aria-disabled',String(option.disabled));
   item.classList.toggle('is-selected',option.selected);
   item.onclick=event=>{event.preventDefault();event.stopPropagation();choose(i)};
   return item;
  });menu.replaceChildren(...items);
 }
 function position(){
  if(menu.hidden)return;
  const rect=trigger.getBoundingClientRect(),edge=12,gap=6;
  const below=innerHeight-rect.bottom-edge-gap,above=rect.top-edge-gap;
  const upwards=below<180&&above>below;
  const available=Math.max(60,upwards?above:below);
  const height=Math.min(320,available),width=Math.min(rect.width,innerWidth-edge*2);
  menu.style.width=width+'px';menu.style.left=Math.max(edge,Math.min(rect.left,innerWidth-width-edge))+'px';
  menu.style.maxHeight=height+'px';menu.style.top='';menu.style.bottom='';
  if(upwards)menu.style.bottom=(innerHeight-rect.top+gap)+'px';else menu.style.top=(rect.bottom+gap)+'px';
 }
 function open(){
  if(trigger.disabled)return;
  if(openSelect&&openSelect!==control)openSelect.close();
  renderOptions();menu.hidden=false;openSelect=control;trigger.setAttribute('aria-expanded','true');position();focusOption(select.selectedIndex);
 }
 const control={sync,close,position};customSelects.push(control);
 trigger.onclick=event=>{event.preventDefault();menu.hidden?open():close()};
 trigger.onkeydown=event=>{
  if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
   event.preventDefault();if(menu.hidden)open();
   const indices=[...select.options].flatMap((option,i)=>option.disabled?[]:[i]);
   let cursor=indices.indexOf(active);
   if(event.key==='Home')cursor=0;else if(event.key==='End')cursor=indices.length-1;
   else cursor=Math.max(0,Math.min(indices.length-1,cursor+(event.key==='ArrowDown'?1:-1)));
   focusOption(indices[cursor]);
  }else if(event.key==='Enter'||event.key===' '){event.preventDefault();menu.hidden?open():choose(active)}
  else if(event.key==='Escape'){event.preventDefault();close()}
  else if(event.key==='Tab')close();
 };
 select.addEventListener('change',sync);
 new MutationObserver(sync).observe(select,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden','disabled','selected']});
 control.contains=target=>wrapper.contains(target);sync();
}
document.querySelectorAll('select').forEach(enhanceSelect);
document.addEventListener('pointerdown',event=>{if(openSelect&&!openSelect.contains(event.target))openSelect.close()});
document.addEventListener('scroll',()=>openSelect?.position(),true);
window.addEventListener('resize',()=>openSelect?.position());
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('toggle',syncCustomSelects));
const renderWithSelects=renderJob;
renderJob=function(job){renderWithSelects(job);syncCustomSelects()};
