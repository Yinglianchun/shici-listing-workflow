// Editable, searchable model choices; do not rely on Qt's native datalist popup.
function enhanceModelInput(input,kind){
 const wrapper=el('div',undefined,'model-picker');input.before(wrapper);wrapper.append(input);input.removeAttribute('list');
 input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-expanded','false');input.autocomplete='off';
 const button=el('button',undefined,'model-picker-toggle');button.type='button';button.setAttribute('aria-label','选择'+(kind==='chat'?'LLM':'embedding')+'模型');button.append(el('span','','select-chevron'));
 const menu=el('div',undefined,'select-menu model-picker-menu');menu.id=input.id+'-choices';menu.role='listbox';menu.hidden=true;
 input.setAttribute('aria-controls',menu.id);wrapper.append(button,menu);
 let query='',choices=[],active=-1,loadError='',loading=false;
 function close(){menu.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');if(openSelect===control)openSelect=null}
 function position(){
  if(menu.hidden)return;const rect=wrapper.getBoundingClientRect(),edge=12,gap=6;
  const below=innerHeight-rect.bottom-edge-gap,above=rect.top-edge-gap,up=below<160&&above>below;
  menu.style.width=Math.min(rect.width,innerWidth-edge*2)+'px';menu.style.left=Math.max(edge,Math.min(rect.left,innerWidth-menu.offsetWidth-edge))+'px';
  menu.style.maxHeight=Math.min(300,Math.max(80,up?above:below))+'px';menu.style.top='';menu.style.bottom='';
  if(up)menu.style.bottom=(innerHeight-rect.top+gap)+'px';else menu.style.top=(rect.bottom+gap)+'px';
 }
 function select(index){if(!choices[index])return;input.value=choices[index];input.focus();close();input.dispatchEvent(new Event('change',{bubbles:true}))}
 function render(){
  choices=(modelLists?.[kind]||[]).filter(name=>name.toLowerCase().includes(query.toLowerCase()));
  menu.replaceChildren();active=-1;
  if(loading||loadError||!choices.length){const note=el('div',loading?'正在获取模型…':loadError||'没有匹配项，可直接填写完整模型 ID。','model-picker-note');menu.append(note)}
  if(loadError){const retry=el('button','重新获取','model-picker-retry');retry.type='button';retry.onclick=()=>load(true);menu.append(retry)}
  for(const [i,name] of choices.entries()){
   const option=el('div',name,'select-option');option.id=input.id+'-choice-'+i;option.role='option';option.setAttribute('aria-selected',String(name===input.value));option.classList.toggle('is-selected',name===input.value);
   option.onpointerdown=e=>e.preventDefault();option.onclick=()=>select(i);menu.append(option);
  }
  position();
 }
 async function load(refresh=false){loading=true;loadError='';render();try{await loadModelLists(refresh)}catch(e){loadError=e.message}finally{loading=false;if(!menu.hidden)render()}}
 function open(){if(openSelect&&openSelect!==control)openSelect.close();query='';menu.hidden=false;input.setAttribute('aria-expanded','true');openSelect=control;render();if(!modelLists)load()}
 const control={close,position,contains:target=>wrapper.contains(target)};
 button.onclick=()=>{if(menu.hidden){open();input.focus()}else close()};
 input.oninput=()=>{query=input.value;if(menu.hidden){menu.hidden=false;input.setAttribute('aria-expanded','true');if(openSelect&&openSelect!==control)openSelect.close();openSelect=control}render();if(!modelLists&&!loading)load()};
 input.onkeydown=event=>{
  if(event.key==='Escape'){close();return}if(event.key==='Tab'){close();return}
  if(event.key==='ArrowDown'||event.key==='ArrowUp'){
   event.preventDefault();if(menu.hidden)open();if(!choices.length)return;
   active=Math.max(0,Math.min(choices.length-1,active+(event.key==='ArrowDown'?1:-1)));
   [...menu.querySelectorAll('[role=option]')].forEach((node,i)=>node.classList.toggle('is-active',i===active));
   const option=$(input.id+'-choice-'+active);input.setAttribute('aria-activedescendant',option.id);option.scrollIntoView({block:'nearest'});
  }else if(event.key==='Enter'&&!menu.hidden&&active>=0){event.preventDefault();select(active)}
 };
 input.addEventListener('focus',()=>{if(menu.hidden)open()});
 document.addEventListener('model-options-changed',()=>{if(!menu.hidden&&!loading)render()});
 const dialog=input.closest('dialog');if(dialog)dialog.addEventListener('close',close);
}
for(const [id,kind] of [['llmModel','chat'],['dialogLlm','chat'],['embeddingModel','embedding'],['dialogEmbedding','embedding']])enhanceModelInput($(id),kind);
