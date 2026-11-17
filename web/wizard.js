// Reuse the existing form controls and pipeline; show one decision at a time.
let wizardStep=0;
const wizardNames=['本次做到哪里','导入拓词','确认本品资料','模型与开始'];
const stageNames=['导入与基础去重','相似素材排序分组','高重合素材去重','本品适用性筛选','方向分类与属性分级','独立QA选题与回答','短语清洗与本品复核','前缀整理与广告词','描述组合与导出'];
const stageHelp=['不调用AI。保留全部来源，先去掉完全重复的文本。','只用embedding与程序比较文字重合度、排序分组，不调用LLM，不删除。','完整相似组装批，不切断组。重复表达剔除；问题完整包含另一问题时保留信息更多的原句，各有独有信息则都保留。','对去重后留下的素材核对本品详情；待补资料问句仍可进入QA。','给去重后的原句分类和分级；完整来源仍可追溯。','从去重前的完整原问及全部变体中独立选QA，不按等级挑选。','清洗后重新对照本品完整资料，检查新功能和丢失的条件。','广告词保留完整，描述素材才整理共同前缀。','按现有素材分组组合描述，每组不超字符上限；超出继续分组，核对父子体后分配。'];
const grid=document.querySelector('.workspace-grid');
const originalPapers=[...document.querySelectorAll('.form-column>.paper')];
const runCard=document.querySelector('.run-card');
const wizard=document.createElement('section');wizard.className='wizard';
wizard.innerHTML='<nav id="wizardNav" class="wizard-nav" aria-label="新建整理步骤"></nav><div id="wizardBody"></div><footer class="wizard-footer"><button id="wizardBack" class="quiet">← 上一步</button><span id="wizardCount"></span><button id="wizardNext" class="primary">下一步 →</button></footer>';
grid.before(wizard);
const panels=wizardNames.map((name,i)=>{const section=document.createElement('section');section.className='wizard-panel';section.dataset.step=i;section.hidden=i!==0;$('wizardBody').append(section);return section});
const goal=document.createElement('div');goal.className='goal-panel';
goal.innerHTML='<p class="eyebrow">ONE STEP AT A TIME</p><h2>这次，先做到这里。</h2><p class="intro">每一步都会保存Excel。可以先整理文件，再把续做提示词交给你常用的AI。</p><div id="goalFields"></div><p id="goalHelp" class="goal-help"></p>';
panels[0].append(goal);
const until=$('until');until.replaceChildren(...stageNames.map((name,i)=>{const o=document.createElement('option');o.value=i+1;o.textContent=String(i+1).padStart(2,'0')+' · '+name;return o}));until.value='1';
until.setAttribute('aria-label','处理到哪一步');
for(const node of [...until.closest('label').childNodes])if(node.nodeType===Node.TEXT_NODE)node.remove();
$('goalFields').append(until.closest('label'),$('maxCharacters').closest('label'));
until.onchange=()=>{$('goalHelp').textContent=stageHelp[Number(until.value)-1];$('maxCharacters').closest('label').hidden=Number(until.value)<9};until.onchange();
panels[1].append(originalPapers[0]);panels[2].append(originalPapers[1]);
panels[2].append($('exampleProduct'));
panels[3].append(runCard);
runCard.querySelector('.eyebrow').textContent='READY WHEN YOU ARE';runCard.querySelector('h2').textContent='确认后开始';
runCard.querySelectorAll('.divider').forEach(e=>e.remove());
grid.remove();
function setWizardStep(step){
 wizardStep=step;panels.forEach((p,i)=>p.hidden=i!==step);
 $('wizardNav').replaceChildren(...wizardNames.map((name,i)=>{const b=document.createElement('button');b.textContent=String(i+1).padStart(2,'0')+' '+name;b.className=i===step?'current':'';b.setAttribute('aria-current',i===step?'step':'false');b.disabled=i>step+1;b.onclick=()=>{if(i<=wizardStep||validateWizard(wizardStep))setWizardStep(i)};return b}));
 $('wizardBack').hidden=step===0;$('wizardNext').hidden=step===3;$('wizardCount').textContent=String(step+1).padStart(2,'0')+' / 04';
 document.querySelector('#createView h1').textContent=wizardNames[step];
 document.querySelector('#createView .page-heading .intro').textContent=['少一点等待，多一点可用的结果。','保留原文和来源，从这里开始整理。','接下来的筛选和回答，都会以这份资料为依据。','做到选定阶段就停，完成的文件会自动保存。'][step];
 if(step===3){$('inlineModels').textContent=Number(until.value)===1?'本次不调用AI；模型可以稍后再设置':'连接与模型列表 ↗'}
}
function validateWizard(step){if(step===1&&!files.length){toast('先选至少一份CSV，再继续。');return false}if(step===2&&(!$('asin').value.trim()||!$('details').value.trim())){toast('请填写本品ASIN和完整详情。');return false}return true}
$('wizardNext').onclick=()=>{if(validateWizard(wizardStep))setWizardStep(wizardStep+1)};
$('wizardBack').onclick=()=>setWizardStep(wizardStep-1);
$('newProject').addEventListener('click',()=>setWizardStep(0));
setWizardStep(0);

const handoff=document.createElement('section');handoff.id='handoffPanel';handoff.className='handoff-panel';
handoff.innerHTML='<div class="handoff-heading"><div><p class="eyebrow">TAKE IT FROM HERE</p><h2>到这里，也可以先停下。</h2></div><button id="openWorkspace" class="quiet">打开工作区 ↗</button></div><p id="workspacePath" class="workspace-path"></p><div class="handoff-controls"><button id="copyHandoff" class="primary">复制接下来步骤的提示词</button><button id="showHandoff" class="quiet">查看提示词</button></div><pre id="handoffText" hidden></pre><p class="field-note">人工续做保存在项目内的「人工续做」。程序继续不会自动读回人工编辑的Excel。</p>';
$('jobView').append(handoff);
const continuation=document.createElement('select');continuation.id='continueUntil';continuation.setAttribute('aria-label','继续处理到哪一步');
stageNames.forEach((name,i)=>{const o=document.createElement('option');o.value=i+1;o.textContent='继续到 '+String(i+1).padStart(2,'0')+' · '+name;continuation.append(o)});
$('continueJob').before(continuation);
$('continueJob').textContent='继续 →';
let handoffPrompt='';
async function loadHandoff(){const data=await api('/api/job/'+activeJob+'/handoff');handoffPrompt=data.prompt;$('handoffText').textContent=handoffPrompt;return data}
$('copyHandoff').onclick=async()=>{try{await loadHandoff();await copyText(handoffPrompt);toast('已复制；提示词也保存在项目内的“接下来怎么做.txt”。')}catch(e){$('handoffText').hidden=false;toast('可展开提示词后手动复制。'+e.message)}};
$('showHandoff').onclick=async()=>{try{await loadHandoff();$('handoffText').hidden=!$('handoffText').hidden;$('showHandoff').textContent=$('handoffText').hidden?'查看提示词':'收起提示词'}catch(e){toast(e.message)}};
$('openWorkspace').onclick=async()=>{try{await api('/api/job/'+activeJob+'/open-folder',{})}catch(e){toast(e.message)}};
const previousRender=renderJob;
renderJob=function(job){
 previousRender(job);
 $('workspacePath').textContent=job.workspace||'';
 const done=job.status.steps.filter(s=>s.state==='done').length;
 const next=Math.min(done+1,9);
 const signature=job.id+':'+done+':'+job.status.state;
 if(continuation.dataset.signature!==signature){continuation.replaceChildren(...job.status.steps.map((step,i)=>{const option=document.createElement('option');option.value=i+1;option.textContent='继续到 '+String(i+1).padStart(2,'0')+' · '+step.name;return option}));continuation.value=String(next);continuation.dataset.signature=signature}
 [...continuation.options].forEach(o=>o.disabled=Number(o.value)<next);
 continuation.hidden=isRunning||done===9;
 $('handoffPanel').hidden=isRunning;
 $('handoffText').hidden=true;
 $('showHandoff').textContent='查看提示词';
 $('handoffPanel').querySelector('h2').textContent=done===9?'文件已保存，接下来核对内容。':'到这里，也可以先停下。';
};
$('continueJob').onclick=async()=>{try{await api('/api/job/'+activeJob+'/run',{until:Number(continuation.value)});await refreshJob()}catch(e){toast(e.message)}};
