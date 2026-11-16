import fs from 'node:fs/promises';
import {chromium} from 'playwright-core';
const [profile,appUrl]=process.argv.slice(2);
const port=Number((await fs.readFile(profile+'/DevToolsActivePort','utf8')).split('\n')[0]);
const browser=await chromium.connectOverCDP('http://127.0.0.1:'+port);
const page=browser.contexts()[0].pages().find(p=>p.url().startsWith(appUrl));
if(!page)throw Error('独立窗口页面未打开');
await page.waitForSelector('#start');
await page.screenshot({path:'output/workbench-desktop.png',fullPage:false});
const session=await browser.newBrowserCDPSession();
const targets=await session.send('Target.getTargets');
const target=targets.targetInfos.find(t=>t.type==='page'&&t.url.startsWith(appUrl));
await session.send('Target.closeTarget',{targetId:target.targetId});
await browser.close().catch(()=>{});
let closed=false;
for(let i=0;i<20;i++){
 try{await fetch(appUrl)}catch{closed=true;break}
 await new Promise(r=>setTimeout(r,500));
}
if(!closed)throw Error('窗口关闭后，后台仍在运行');
console.log('独立窗口正常显示；关闭最后一个应用窗口后，后台端口已退出。');
