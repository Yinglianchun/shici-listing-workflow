// Motion reference: local ThoughtLine + StatusMark; plain DOM, with real server states.
const statusMarkup='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle class="status-ring" cx="12" cy="12" r="9"/><path class="status-check" pathLength="1" d="M7.5 12.25 10.5 15.25 16.75 8.75"/><path class="status-cross" pathLength="1" d="M8.5 8.5 15.5 15.5M15.5 8.5 8.5 15.5"/></svg>';
function statusIcon(state){const span=el('span',undefined,'status-symbol');span.dataset.state=state;span.innerHTML=statusMarkup;return span}
function setStatus(icon,state){
 const previous=icon.dataset.state;if(previous===state)return;
 const ring=icon.querySelector('.status-ring'),transform=getComputedStyle(ring).transform;
 icon.dataset.state=state;
 if(previous==='running'&&state!=='running'&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
  const matrix=new DOMMatrix(transform),angle=(Math.atan2(matrix.b,matrix.a)*180/Math.PI+360)%360;
  ring.animate([{transform:'rotate('+angle+'deg)'},{transform:'rotate(360deg)'}],{duration:240,easing:'cubic-bezier(.23,1,.32,1)'});
 }
}
const runStatus=el('details',undefined,'run-status');runStatus.id='runStatus';
const runSummary=el('summary'),runIcon=statusIcon('pending'),runLabel=el('span',undefined,'run-status-label'),runCounter=el('span',undefined,'run-status-count'),runTimer=el('span',undefined,'run-status-time');
runSummary.append(runIcon,runLabel,runCounter,runTimer);runStatus.append(runSummary);
const runList=el('ol',undefined,'run-status-list');runStatus.append(runList);
document.querySelector('#jobView>.page-heading').after(runStatus);
let liveJob=null,runIdentity='';
function updateRunTime(){
 if(!liveJob?.status.started_at){runTimer.textContent='';return}
 const seconds=Math.max(0,Math.floor((liveJob.status.ended_at||Date.now()/1000)-liveJob.status.started_at));
 runTimer.textContent=seconds<60?seconds+'秒':Math.floor(seconds/60)+'分'+seconds%60+'秒';
}
const renderWithoutStatus=renderJob;
renderJob=function(job){
 renderWithoutStatus(job);liveJob=job;
 const state=job.status.state;
 setStatus(runIcon,state==='running'?'running':['completed','paused'].includes(state)?'done':state==='failed'?'failed':'cancelled');
 const current=job.status.steps.find(s=>s.state==='running');
 runLabel.textContent=state==='running'?(job.status.product_analysis_state==='running'?'正在分析本品卖点与资料冲突':current?'正在'+current.name:'正在准备'):state==='completed'?'本次整理已完成':state==='paused'?'已完成选定步骤':state==='failed'?'处理未完成':'已停止，文件已保留';
 runCounter.textContent=state==='running'&&job.progress?'已处理 '+job.progress.done+' / '+job.progress.total:'';
 runSummary.setAttribute('aria-label',runLabel.textContent+'，展开查看各阶段');
 if(runIdentity!==job.id){runList.replaceChildren(...job.status.steps.map(()=>{const li=el('li');li.append(statusIcon('pending'),el('span'),el('small'));return li}));runIdentity=job.id}
 job.status.steps.forEach((step,i)=>{
  const row=runList.children[i];let status=step.state;
  if(status==='running'&&state==='failed')status='failed';
  if(status==='running'&&state==='stopped')status='cancelled';
  setStatus(row.children[0],status);row.children[1].textContent=String(i+1).padStart(2,'0')+' '+step.name;
  row.children[2].textContent={pending:'未开始',running:'处理中',done:'已保存',failed:'未完成',cancelled:'已停止'}[status]||'';
 });
 $('jobState').hidden=true;updateRunTime();
};
setInterval(updateRunTime,1000);
for(const id of ['connectOnboarding','fetchModels','captureProduct','start']){
 const button=$(id);if(!button)continue;
 const sync=()=>{button.classList.toggle('request-working',button.disabled);button.setAttribute('aria-busy',String(button.disabled))};
 new MutationObserver(sync).observe(button,{attributes:true,attributeFilter:['disabled']});sync();
}
