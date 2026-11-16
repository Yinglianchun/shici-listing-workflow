// The opening is deliberately a blank, single-purpose page.
document.title='拾词';
const welcome=document.createElement('section');welcome.id='welcomeView';
welcome.innerHTML='<div class="welcome-content"><h1>开始整理</h1><p>关键词 · 问答 · 商品描述</p><button id="beginFlow" class="welcome-begin">start</button></div><footer class="welcome-links"><button id="openHistory">继续上次</button><button id="welcomeModels">模型设置</button></footer>';
document.querySelector('main').prepend(welcome);
const historyDialog=document.createElement('dialog');historyDialog.id='historyDialog';
historyDialog.innerHTML='<form method="dialog" class="dialog-top"><h2>继续上次</h2><button aria-label="关闭">×</button></form>';
historyDialog.append($('history'));document.body.append(historyDialog);
const smallMenu=document.createElement('div');smallMenu.className='small-menu';
smallMenu.innerHTML='<button id="flowSettings" aria-label="模型设置">···</button>';
document.querySelector('main').prepend(smallMenu);
const apiGuide=document.createElement('section');apiGuide.id='apiGuide';apiGuide.hidden=true;
apiGuide.innerHTML='<div class="api-guide-content"><h2 class="numbered-heading">填写 <span class="api-key-highlight">API Key</span></h2><p class="intro">使用硅基流动的 API Key，连接后可以选择模型。</p><p class="api-guide-help">还没有密钥？在硅基流动账户的「API 密钥」中创建，再粘贴到这里。</p><label for="onboardingKey" class="sr-only">硅基流动 API Key</label><div class="api-key-line"><input id="onboardingKey" type="password" autocomplete="off" placeholder="粘贴 API Key"><button id="connectOnboarding" class="quiet">连接</button></div></div><footer class="api-guide-footer"><button id="skipOnboarding" class="text-button">稍后填写</button><button id="nextOnboarding" aria-label="继续" disabled>→</button></footer>';
document.querySelector('main').append(apiGuide);
function enterFlow(){if(!apiGuide.hidden){setWizardStep(0);return}newView();setWizardStep(0);apiGuide.hidden=true;$('welcomeView').hidden=true;smallMenu.hidden=false;document.title='拾词'}
function showWelcome(){activeJob=null;isRunning=false;apiGuide.hidden=true;$('welcomeView').hidden=false;$('createView').hidden=true;$('jobView').hidden=true;smallMenu.hidden=true;window.history.replaceState({},'','/');document.title='拾词'}
$('beginFlow').onclick=async()=>{const button=$('beginFlow');button.disabled=true;try{if(window.hasApiKey===undefined)setSettings(await api('/api/bootstrap'));if(window.hasApiKey){onboardingOffset=0;refreshNumberedHeadings();enterFlow()}else{onboardingOffset=1;refreshNumberedHeadings();await moveStep(welcome.querySelector('.welcome-content'),()=>apiGuide.querySelector('.api-guide-content'),()=>{$('welcomeView').hidden=true;$('createView').hidden=true;$('jobView').hidden=true;apiGuide.hidden=false;smallMenu.hidden=false;$('nextOnboarding').disabled=true;$('onboardingKey').focus()})}}catch(e){toast(e.message)}finally{button.disabled=false}};
$('connectOnboarding').onclick=async()=>{const button=$('connectOnboarding'),input=$('onboardingKey');if(!input.value.trim()){toast('请先粘贴 API Key。');input.focus();return}button.disabled=true;$('nextOnboarding').disabled=true;try{const settings=await api('/api/settings',{api_key:input.value.trim()});input.value='';input.closest('.api-key-line').classList.remove('has-value');setSettings(settings);await loadModelLists(true);toast('已连接，可以继续。');$('nextOnboarding').disabled=false;button.textContent='已连接'}catch(e){window.hasApiKey=false;toast(e.message);button.textContent='重新连接'}finally{button.disabled=false}};
$('onboardingKey').addEventListener('input',event=>{event.currentTarget.closest('.api-key-line').classList.toggle('has-value',!!event.currentTarget.value.trim());$('nextOnboarding').disabled=true;$('connectOnboarding').textContent='连接'});
$('onboardingKey').addEventListener('keydown',event=>{if(event.key==='Enter')$('connectOnboarding').click()});
$('nextOnboarding').onclick=enterFlow;$('skipOnboarding').onclick=enterFlow;
$('openHistory').onclick=()=>historyDialog.showModal();
$('welcomeModels').onclick=showSettings;$('flowSettings').onclick=showSettings;
historyDialog.addEventListener('click',event=>{if(event.target.closest('#history button')){historyDialog.close();$('welcomeView').hidden=true;smallMenu.hidden=false}});
const originalSetStep=setWizardStep;
let onboardingOffset=0;
// Step progress sits above the centered title: dots plus "第 N 步 / 共 M 步".
function setStepMeta(heading,index,total){const anchor=heading.closest(".section-title")||heading;let meta=anchor.previousElementSibling;if(!meta||!meta.classList.contains("step-meta")){meta=el("div",undefined,"step-meta");anchor.before(meta)}const dots=el("div",undefined,"step-dots");dots.setAttribute("aria-hidden","true");for(let i=1;i<=total;i++)dots.append(el("i",undefined,i===index?"on":""));meta.replaceChildren(dots,el("p","第 "+index+" 步 / 共 "+total+" 步","step-label"))}
function numberedHeading(step,title){const heading=panels[step].querySelector("h2");heading.classList.add("numbered-heading");heading.textContent=title}
function refreshNumberedHeadings(){['要处理到哪一步？','导入拓词文件','填写商品资料','选择模型'].forEach((title,i)=>numberedHeading(i,title))}
setWizardStep=function(step){originalSetStep(step);$('wizardBack').textContent='上一步';$('wizardBack').setAttribute('aria-label','上一步');$('wizardNext').textContent='→';$('wizardNext').setAttribute('aria-label','下一步');$('wizardCount').textContent='';
 if(step===3){const needsAI=Number(until.value)>1;for(const id of ['llmModel','embeddingModel'])$(id).closest('label').hidden=!needsAI;$('inlineModels').hidden=!needsAI;numberedHeading(3,needsAI?'选择模型':'确认并开始')}
 window.scrollTo(0,0)};
setStepMeta(apiGuide.querySelector("h2"),1,5);
numberedHeading(0,'要处理到哪一步？');
document.querySelector('.goal-panel>.intro').textContent='选择本次处理的最后一个阶段。';
document.querySelector('.goal-panel>.eyebrow').remove();
// Product retrieval comes first; the longer editable details stay one click away.
const productPanel=panels[2],paper=productPanel.querySelector('.paper');
const detailEditor=document.createElement('details');detailEditor.className='product-editor';
detailEditor.innerHTML='<summary>手动填写 / 核对完整资料</summary>';
const firstDetail=paper.querySelector('.two-fields');
while(firstDetail.nextSibling)detailEditor.append(firstDetail.nextSibling);
detailEditor.prepend(firstDetail);paper.append(detailEditor);detailEditor.append($('exampleProduct'));
document.querySelector('#details').rows=6;
const analysisHint=el('p','进入AI整理前，会先分析本品定位、卖点、适用人群与资料冲突，保留对应原文。只做导入或排序时，可暂不调用LLM。','field-note');
paper.append(analysisHint);
numberedHeading(1,'导入拓词文件');numberedHeading(2,'填写商品资料');numberedHeading(3,'选择模型');
const originalValidate=validateWizard;
validateWizard=function(step){const valid=originalValidate(step);if(!valid&&step===2)detailEditor.open=true;return valid};
runCard.querySelectorAll(':scope>.field-note').forEach((node,i)=>{if(i===0)node.remove()});
const minimalRender=renderJob;
const stagePicker=document.createElement('select');stagePicker.id='resultStage';stagePicker.setAttribute('aria-label','查看哪个阶段');
document.querySelector('.results-head').append(stagePicker);
stagePicker.onchange=async()=>{selectedStage=Number(stagePicker.value);await refreshJob()};
const tablePreview=document.createElement('details');tablePreview.className='table-preview';tablePreview.innerHTML='<summary>查看表格内容</summary>';
$('preview').before(tablePreview);tablePreview.append($('searchRows'),$('preview'));
renderJob=function(job){minimalRender(job);$('welcomeView').hidden=true;smallMenu.hidden=false;document.title='拾词'};
const detailRender=renderJob;
renderJob=function(job){detailRender(job);$('handoffPanel').querySelector('h2').textContent='保存与续做';stagePicker.replaceChildren(...job.status.steps.flatMap((step,i)=>{if(step.state==='pending'&&i+1!==selectedStage)return [];const option=document.createElement('option');option.value=i+1;option.textContent=String(i+1).padStart(2,'0')+' · '+step.name;return [option]}));stagePicker.value=String(selectedStage)};
// Preserve direct links to existing projects, otherwise start on the quiet welcome.
if(!new URLSearchParams(location.search).get('job'))showWelcome();else welcome.hidden=true;

const nextPill='继续<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="arrow-shaft" d="M5 12h10"/><path d="M13 6l6 6-6 6"/></svg>';
for(const id of ['nextOnboarding','wizardNext']){$(id).classList.add('design-next');$(id).innerHTML=nextPill}
const setStepWithPill=setWizardStep;
const wizardMeta=el('div',undefined,'step-meta');
const wizardDots=el('div',undefined,'step-dots');wizardDots.setAttribute('aria-label','整理步骤');
const wizardStepLabel=el('p',undefined,'step-label');
wizardMeta.append(wizardDots,wizardStepLabel);$('wizardBody').before(wizardMeta);
function updateWizardProgress(step){
 const total=4+onboardingOffset;
 if(wizardDots.children.length!==total)wizardDots.replaceChildren(...Array.from({length:total},(_,i)=>{
  const dot=el('button');dot.type='button';
  dot.setAttribute('aria-label',i<onboardingOffset?'填写 API Key':wizardNames[i-onboardingOffset]);
  dot.onclick=()=>{
   if(i<onboardingOffset){showApiStep();return}
   setWizardStep(i-onboardingOffset);
  };
  return dot;
 }));
 [...wizardDots.children].forEach((dot,i)=>{dot.classList.toggle('on',i===step+onboardingOffset);dot.setAttribute('aria-current',i===step+onboardingOffset?'step':'false')});
 wizardStepLabel.textContent='第 '+(step+1+onboardingOffset)+' 步 / 共 '+total+' 步';
}
setWizardStep=function(step){setStepWithPill(step);$('wizardNext').innerHTML=nextPill;updateWizardProgress(step);if(window.syncCustomSelects)syncCustomSelects()};
updateWizardProgress(wizardStep);
const setStepImmediately=setWizardStep;
let pageTransition=0,pageAnimations=[],outgoingCopies=[];
function stopPageAnimations(){for(const animation of pageAnimations)animation.cancel();pageAnimations=[];for(const copy of outgoingCopies)copy.remove();outgoingCopies=[]}
function clearPageOpacity(){
 $('wizardBody').style.removeProperty('opacity');apiGuide.style.removeProperty('opacity');
 for(const node of document.querySelectorAll('[data-step-fade]')){node.style.removeProperty('opacity');node.removeAttribute('data-step-fade')}
}
function visualCopy(source){
 if(!source||!source.getBoundingClientRect().height)return null;
 const rect=source.getBoundingClientRect(),copy=source.cloneNode(true);
 copy.removeAttribute('id');copy.querySelectorAll('[id]').forEach(node=>node.removeAttribute('id'));
 copy.setAttribute('aria-hidden','true');copy.inert=true;copy.classList.add('motion-outgoing');
 Object.assign(copy.style,{position:'fixed',left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px',margin:'0'});
 document.body.append(copy);outgoingCopies.push(copy);return copy;
}
async function moveStep(source,destination,change,direction=1){
 const request=++pageTransition;stopPageAnimations();clearPageOpacity();
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const copy=reduced?null:visualCopy(source);
 change();
 const incoming=destination();
 if(reduced)return;
 const timing={duration:240,easing:'cubic-bezier(.23,1,.32,1)'};
 if(copy)pageAnimations.push(copy.animate([{transform:'translateX(0)',opacity:1},{transform:'translateX('+(-direction*16)+'px)',opacity:0}],timing));
 if(incoming)pageAnimations.push(incoming.animate([{transform:'translateX('+(direction*16)+'px)',opacity:.35},{transform:'translateX(0)',opacity:1}],timing));
 await Promise.all(pageAnimations.map(a=>a.finished.catch(()=>{})));
 if(request===pageTransition)stopPageAnimations();
}
async function showApiStep(){
 const source=panels[wizardStep];
 await moveStep(source,()=>apiGuide.querySelector('.api-guide-content'),()=>{
  updateWizardProgress(-1);$('createView').hidden=true;apiGuide.hidden=false;$('nextOnboarding').disabled=!window.hasApiKey;
  [...apiDots.children].forEach((dot,i)=>{dot.classList.toggle('on',i===0);dot.setAttribute('aria-current',i===0?'step':'false')});
 },-1);
}
setWizardStep=async function(step){
 if(step<0||step>=panels.length)return;
 const fromApi=!apiGuide.hidden,fromWelcome=!welcome.hidden;
 const previous=wizardStep;
 if(!fromApi&&!fromWelcome&&step===previous){setStepImmediately(step);return}
 if(typeof openSelect!=='undefined'&&openSelect)openSelect.close();
 const source=fromApi?apiGuide.querySelector('.api-guide-content'):fromWelcome?welcome.querySelector('.welcome-content'):panels[previous];
 await moveStep(source,()=>panels[step],()=>{
  if(fromApi){newView();apiGuide.hidden=true}
  setStepImmediately(step);
 },step<previous?-1:1);
};
const showWelcomeWithoutTransition=showWelcome;
showWelcome=function(){pageTransition++;stopPageAnimations();clearPageOpacity();showWelcomeWithoutTransition()};
const apiDots=apiGuide.querySelector('.step-dots');apiDots.removeAttribute('aria-hidden');
apiDots.replaceChildren(...Array.from({length:5},(_,i)=>{
 const button=el('button');button.type='button';button.className=i===0?'on':'';
 button.setAttribute('aria-label',i===0?'填写 API Key':wizardNames[i-1]);
 button.setAttribute('aria-current',i===0?'step':'false');
 button.onclick=()=>{if(i>0){[...apiDots.children].forEach((dot,index)=>dot.classList.toggle('on',index===i));setWizardStep(i-1)}};
 return button;
}));
const restart=el('button','重新整理','quiet restart-button');restart.id='restartFlow';
restart.onclick=showWelcome;
const resultFooter=el('footer',undefined,'result-footer');resultFooter.append(restart);$('handoffPanel').append(resultFooter);
