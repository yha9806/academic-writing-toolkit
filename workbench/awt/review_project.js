"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const roles = {abstract:"摘要",methods:"方法",results:"结果",discussion:"讨论 / 结论",introduction:"引言",references:"参考文献",other:"其他"};
const states = {draft:"待开始",running:"正在检查",preparing:"正在转换文档",pause_requested:"本批结束后暂停",cancel_requested:"本批结束后取消",paused:"已暂停",cancelled:"已取消",budget_paused:"预算用尽，已暂停",failed:"失败，可重试",interrupted:"中断，可恢复",completed:"计划内批次已完成",corrupt:"检查点不可读"};
const stepStates = {pending:"尚未检查",running:"请求执行中",completed:"已保存",failed:"失败，未计为已检查",uncertain:"请求结果不明"};
const phases = {text:"文字精读",chapter:"章节索引汇总",cross:"跨章节关联",vision:"所选图像"};
const activeStates = ["running","pause_requested","cancel_requested"];
let job=null, timer=null, selectedAssets=new Set(), activeLayout=null, layoutPreview=null, sourceFilters={};
let revisionShown=null, currentSourceAsset=null, uploadBusy=false;
const views = {};

function error(message) {$("error").textContent=message||"";$("error").hidden=!message;}
async function post(path,payload={}) {
  const response=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({compact:true,...payload})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||"请求失败");return data;
}
async function guarded(action) {error("");try{await action();}catch(failure){error(failure.message);}}
function modelLabel(value){return value.provider+" / "+(value.requested_model||"CLI 默认模型")+(value.base_url?" · "+value.base_url:"");}
function encoded(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]);reader.onerror=()=>reject(new Error("浏览器无法读取所选文件，请重新选择后重试"));reader.readAsDataURL(blob);});}
async function upload(file,status) {
  if(!file.size||file.size>80000000)throw new Error("单份材料需为 1 字节至 80 MB");
  const transfer=await post("/api/project/upload/start",{filename:file.name,size:file.size});
  let offset=0;
  while(offset<file.size){
    const part=await encoded(file.slice(offset,offset+transfer.chunk_bytes));
    const result=await post("/api/project/upload/chunk",{upload_id:transfer.upload_id,offset,content_base64:part});
    offset=result.offset;status.textContent=file.name+" · 已上传 "+Math.round(offset/file.size*100)+"%";
  }
  return {upload_id:transfer.upload_id};
}
async function uploads(files,status){
  if(!files.length||files.length>20||files.reduce((sum,f)=>sum+f.size,0)>160000000)throw new Error("请选择 1–20 份文件，总计不超过 160 MB");
  const result=[];for(const file of files)result.push(await upload(file,status));return result;
}
function budget(){return {profile:$("profile").value,max_calls:Number($("max-calls").value),total_tokens:Number($("total-tokens").value),
  input_price_per_million:$("input-price").value===""?null:Number($("input-price").value),output_price_per_million:$("output-price").value===""?null:Number($("output-price").value)};}
$("profile").onchange=()=>{const values={economy:[12,65000,"4,000 输入 / 1,200 输出"],legacy:[8,26000,"2,400 输入 / 800 输出"],balanced:[24,250000,"8,000 输入 / 2,200 输出"]}[$("profile").value];$("max-calls").value=values[0];$("total-tokens").value=values[1];$("profile-note").textContent="每批约 "+values[2]+" token；图像默认不发送。";};
$("import").onclick=()=>guarded(async()=>{
  if(uploadBusy)return;uploadBusy=true;$("import").disabled=true;
  try{const files=await uploads([...$("files").files],$("import-status"));$("import-status").textContent="正在本地提取、合并文字区域并规划批次…";
    render(await post("/api/project/import",{files,goal:$("goal").value,budget:budget()}));$("import-status").textContent="材料已保存；检查计划后点击开始才会调用模型。";await loadJobs();
  }catch(failure){$("import-status").textContent="导入未完成，可重新选择文件后重试。";throw failure;}finally{uploadBusy=false;$("import").disabled=false;}
});
async function loadJobs(){
  const response=await fetch("/api/projects"),data=await response.json();if(!response.ok)throw new Error(data.error);
  $("job-list").innerHTML=data.jobs.length?data.jobs.map(item=>'<div class="job-row"><span><strong>'+esc(item.filenames.join("、")||item.goal)+'</strong><br><small>'+esc(states[item.state]||item.state)+' · '+esc(item.updated_at)+'</small></span><button class="secondary" data-restore="'+item.id+'" '+(item.state==="corrupt"?"disabled":"")+'>打开</button></div>').join(""):"本机还没有跨章节任务。";
}
$("job-list").onclick=event=>{const button=event.target.closest("[data-restore]");if(button)guarded(async()=>render(await post("/api/project/status",{job_id:button.dataset.restore})));};

function view(kind,container,renderer,label){
  const target=$(container);target.innerHTML='<div data-items></div><nav class="actions" aria-label="'+label+'分页"><button class="secondary" data-prev>上一页</button><span data-count class="stat"></span><button class="secondary" data-next>下一页</button></nav>';
  const v=views[kind]={kind,target,renderer,label,offset:0,total:0,limit:20,loading:false,again:false};
  target.querySelector("[data-prev]").onclick=()=>{v.offset=Math.max(0,v.offset-v.limit);guarded(()=>loadView(kind));};
  target.querySelector("[data-next]").onclick=()=>{v.offset+=v.limit;guarded(()=>loadView(kind));};
}
function visible(v){for(let e=v.target.parentElement;e;e=e.parentElement){if(e.tagName==="DETAILS"&&!e.open)return false;}return true;}
async function loadView(kind){
  const v=views[kind];if(!job)return;if(v.loading){v.again=true;return;}v.loading=true;
  const query={job_id:job.id,kind,offset:v.offset,limit:v.limit,...(kind==="blocks"?sourceFilters:{})},signature=JSON.stringify(query),revision=job.revision;
  try{
    const data=await post("/api/project/page",query);
    const current={job_id:job?.id,kind,offset:v.offset,limit:v.limit,...(kind==="blocks"?sourceFilters:{})};
    if(!job||job.revision!==revision||data.revision!==revision||JSON.stringify(current)!==signature){v.again=true;return;}
    v.total=data.total;
    if(v.offset>=data.total&&v.offset){v.offset=0;v.again=true;return;}
    v.target.querySelector("[data-items]").innerHTML=data.items.length?v.renderer(data.items):'<p class="empty">当前范围暂无记录。</p>';
    v.target.querySelector("[data-count]").textContent=v.label+" "+(data.total?v.offset+1:0)+"–"+Math.min(v.offset+v.limit,data.total)+" / "+data.total;
    v.target.querySelector("[data-prev]").disabled=v.offset===0;v.target.querySelector("[data-next]").disabled=v.offset+v.limit>=data.total;
  }finally{v.loading=false;if(v.again){v.again=false;if(job&&visible(v))guarded(()=>loadView(kind));}}
}
function quote(anchor){return '<p><button class="secondary" data-locator="'+esc(anchor.locator)+'">'+esc(anchor.location||anchor.locator)+'</button></p><div class="quote">'+esc(anchor.quote||"依据所选图像")+'</div>';}
view("chapters","chapters",items=>items.map(node=>'<article class="claim"><div class="bar"><strong>'+esc(node.filename+" / "+node.title)+'</strong><span class="badge">'+node.checked_blocks+" / "+node.total_blocks+' 区域</span></div><p class="stat">'+(node.page_start?"第 "+node.page_start+"–"+node.page_end+" 页 · ":"")+node.characters.toLocaleString()+" 字符 · "+node.reused_blocks+' 区域沿用已保存结果</p><button class="secondary" data-chapter="'+node.id+'">查看本章原文</button>'+node.summaries.map(s=>'<p>'+esc(s.summary)+'</p>').join("")+'</article>').join(""),"章节");
view("coverage","coverage",items=>'<div class="table-wrap"><table><thead><tr><th>文件 / 章节</th><th>类别</th><th>文字覆盖</th><th>待检查</th></tr></thead><tbody>'+items.map(row=>'<tr><td>'+esc(row.filename+" / "+row.section)+'</td><td>'+(job.state==="draft"&&!job.calls_reserved?'<select aria-label="'+esc(row.filename+" "+row.section+" 类别")+'" data-role-doc="'+row.document_id+'" data-role-section="'+esc(row.section)+'">'+Object.entries(roles).map(([id,label])=>'<option value="'+id+'" '+(id===row.role?"selected":"")+'>'+label+'</option>').join("")+'</select>':esc(roles[row.role]))+'</td><td>'+row.checked_blocks+" / "+row.total_blocks+(row.stale_blocks?" · "+row.stale_blocks+" 处旧要求待复查":"")+'</td><td><button class="secondary" data-unchecked-doc="'+row.document_id+'" data-section="'+esc(row.section)+'">'+row.unchecked_count+' 处未检查</button></td></tr>').join("")+'</tbody></table></div>',"覆盖");
view("cross","cross-coverage",items=>items.map(row=>'<article class="claim"><strong>'+esc(row.pair.map(p=>roles[p]||p).join(" ↔ "))+'</strong><p>'+esc({anchors_reviewed:"已对照所选原文",missing_section:"缺少章节，尚未检查",budget_too_small:"输入预算不足",partial:"部分已对照",pending:"尚未对照"}[row.status]||row.status)+" · "+row.completed_batches+" / "+row.total_batches+" 批 · 纳入 "+row.included_count+' 处</p><button class="secondary" data-cross="'+row.pair_index+'">查看 '+row.omitted_count+' 处未对照区域</button><p class="stat">'+esc(row.scope||"关键锚点对照；不代表全文关联已穷尽")+'</p></article>').join(""),"关联范围");
view("assets","assets",items=>'<div class="asset-list">'+items.map(asset=>'<div class="asset"><input type="checkbox" aria-label="发送 '+esc(asset.location)+' 做视觉检查" data-asset="'+asset.id+'" '+(selectedAssets.has(asset.id)||asset.selected?"checked":"")+' '+(job.state!=="draft"||!job.model.supports_images?"disabled":"")+'><span>'+esc(asset.location)+'<br><small>'+(asset.status==="image_reviewed"?"图像已审阅":"图像尚未检查")+'</small></span><button class="secondary" data-preview="'+asset.id+'" data-label="'+esc(asset.location)+'">本地预览</button></div>').join("")+'</div>',"图像");
view("blocks","blocks",items=>items.map(block=>'<article class="claim"><button class="secondary" data-locator="'+block.id+'">'+esc(block.location)+'</button><p class="stat">'+esc(block.chapter+" / "+block.section)+" · "+(block.status==="text_reviewed"?"分段文字已审阅":"尚未检查")+'</p><div class="quote">'+esc(block.text)+'</div></article>').join(""),"原文");
view("claims","claims",items=>items.map(claim=>'<article class="claim">'+quote(claim)+'<p>'+esc(claim.note)+'</p>'+claim.evidence.map(link=>'<span class="badge">'+esc({supports:"模型判断：支持",conflicts:"模型判断：冲突",context_only:"仅提供语境"}[link.relation])+'</span>'+quote(link)).join("")+(!claim.evidence.length?'<span class="badge unchecked">尚未配对依据</span>':"")+'</article>').join(""),"主张");
view("findings","findings",items=>items.map(item=>'<article class="issue '+esc(item.severity)+'"><strong>'+esc(item.message)+'</strong>'+(item.needs_visual?' <span class="badge">还需视觉核验</span>':"")+item.anchors.map(quote).join("")+'</article>').join(""),"发现");
function stepRows(items){return '<div class="table-wrap"><table><thead><tr><th>范围</th><th>状态</th><th>请求记录</th></tr></thead><tbody>'+items.map(step=>'<tr><td>'+esc(step.label)+'<br><small>'+esc(phases[step.phase]||step.phase)+'</small></td><td>'+esc(stepStates[step.status]||step.status)+(step.reused_from?'<br><small>复用第 '+step.reused_from.revision+' 版结果，无新增调用</small>':"")+'</td><td>'+step.attempts.map(a=>esc(a.status)+" · 输入估算 "+a.input_estimate+" / 输出预算 "+a.output_limit).join("<br>")+'</td></tr>').join("")+'</tbody></table></div>';}
view("steps","steps",stepRows,"批次");view("history","history",stepRows,"历史批次");
document.querySelectorAll("details").forEach(detail=>detail.addEventListener("toggle",()=>{if(detail.open&&job)Object.values(views).filter(v=>detail.contains(v.target)&&visible(v)).forEach(v=>guarded(()=>loadView(v.kind)));}));

function filterSource(filters,label){
  sourceFilters=filters;views.blocks.offset=0;$("source-filter").textContent=label;$("materials-detail").open=true;guarded(()=>loadView("blocks"));$("materials-detail").scrollIntoView({block:"start",behavior:"smooth"});
}
document.addEventListener("click",event=>{
  const button=event.target.closest("button");if(!button)return;
  if(button.dataset.chapter)filterSource({chapter_id:button.dataset.chapter},"当前范围：所选章节");
  if(button.dataset.uncheckedDoc)filterSource({kind:"unchecked",document_id:button.dataset.uncheckedDoc,section:button.dataset.section},"当前范围：所选章节中未检查内容");
  if(button.dataset.cross!==undefined)filterSource({cross_pair:Number(button.dataset.cross)},"当前范围：本组关联未纳入的原文");
  if(button.dataset.locator)guarded(()=>showSource(button.dataset.locator));
  if(button.dataset.preview)guarded(()=>showImage(button.dataset.preview,button.dataset.label));
});
$("coverage").onchange=event=>{if(event.target.dataset.roleDoc)guarded(async()=>render(await post("/api/project/classify",{job_id:job.id,document_id:event.target.dataset.roleDoc,section:event.target.dataset.roleSection,role:event.target.value})));};
$("assets").onchange=event=>{if(event.target.dataset.asset)event.target.checked?selectedAssets.add(event.target.dataset.asset):selectedAssets.delete(event.target.dataset.asset);};
$("search-source").onclick=()=>filterSource({...sourceFilters,search:$("source-search").value},"当前范围：原文搜索");
$("source-search").onkeydown=event=>{if(event.key==="Enter")$("search-source").click();};
$("clear-source").onclick=()=>{$("source-search").value="";filterSource({},"当前范围：全部原文");};
$("unchecked-source").onclick=()=>filterSource({...sourceFilters,kind:"unchecked"},"当前范围：未检查内容");
async function showImage(identifier,label){const data=await post("/api/project/preview",{job_id:job.id,asset_id:identifier});$("preview-image").src="data:"+data.mime_type+";base64,"+data.data_base64;$("preview-label").textContent=label||identifier;$("preview").showModal();}
async function showSource(identifier){
  if(identifier.includes(":page")||identifier.includes(":image"))return showImage(identifier,"所选图像");
  const data=await post("/api/project/page",{job_id:job.id,kind:"locator",locator:identifier,limit:1}),block=data.items[0];
  if(!block)throw new Error("该定位不在当前材料版本中");
  $("source-title").textContent=block.location;$("source-text").textContent=block.text;
  $("source-spans").textContent=(block.source_spans||[]).map(s=>s.locator+" · 字符 "+(s.start+1)+"–"+s.end).join("\n");
  currentSourceAsset=block.preview_asset_id;$("source-preview").hidden=!currentSourceAsset;$("source-dialog").showModal();
}
$("close-source").onclick=()=>$("source-dialog").close();$("close-preview").onclick=()=>$("preview").close();
$("source-preview").onclick=()=>guarded(()=>showImage(currentSourceAsset,$("source-title").textContent));

function render(value){
  if(job&&job.id===value.id&&job.updated_at>value.updated_at)return;
  const changed=!job||job.id!==value.id,revisionChanged=changed||revisionShown!==value.revision;
  job=value;clearTimeout(timer);
  if(changed){selectedAssets=new Set();activeLayout=null;layoutPreview=null;sourceFilters={};Object.values(views).forEach(v=>v.offset=0);}
  if(revisionChanged){sourceFilters={};$("steering").value=job.goal;revisionShown=job.revision;$("resume-calls").value=job.budget.max_calls;$("resume-tokens").value=job.budget.total_tokens;$("retry-uncertain").checked=false;Object.values(views).forEach(v=>v.offset=0);}
  history.replaceState(null,"","/project?job="+job.id);
  ["task","coverage-panel","results","layout-panel"].forEach(id=>$(id).hidden=false);
  $("model").textContent=modelLabel(job.model);$("state").textContent=states[job.state]||job.state;$("state").className="state "+(job.state==="completed"?"good":["failed","budget_paused","interrupted"].includes(job.state)?"warn":"");
  $("task-goal").textContent="第 "+job.revision+" 版要求："+job.goal;
  $("progress").max=Math.max(1,job.progress.planned);$("progress").value=job.progress.completed;
  $("progress-text").textContent="已保存 "+job.progress.completed+" / "+job.progress.planned+" 批"+(job.progress.cross_pending_planning?"；后续关联检查待规划":"")+(job.progress.active?" · "+job.progress.active:"");
  $("cost").textContent="累计调用 "+job.calls_reserved+" / "+job.budget.max_calls+" · 已预留约 "+job.tokens_reserved.toLocaleString()+" token"+(job.estimated_cost_reserved!==null?" · 按填写单价估算 "+job.estimated_cost_reserved:"");
  $("cost-note").textContent=job.cost_note;$("task-error").textContent=job.error||"";
  $("plan-summary").textContent="当前未完成计划："+(job.plan.pending_calls||0)+" 次，预计再预留 "+(job.plan.pending_token_reservation||0).toLocaleString()+" token；"+(job.plan.reused_batches||0)+" 批直接复用。"+(job.plan.note||"");
  $("revision-summary").textContent=job.revision_change.note?"本次修订导入时复用 "+job.revision_change.reused_blocks+" 处已审阅区域，另 "+job.revision_change.pending_blocks+" 处列入复查；当前进度见上方。"+job.revision_change.note:"";
  const active=activeStates.includes(job.state);$("start").disabled=active||job.state==="completed";$("start").textContent=job.state==="draft"?"开始审阅":"继续未完成批次";
  $("pause").disabled=job.state!=="running";$("cancel").disabled=["completed","cancelled","cancel_requested"].includes(job.state);$("revise").disabled=active||uploadBusy;
  $("uncertain-label").hidden=!job.uncertain_requests;
  $("vision-note").textContent=job.model.supports_images?"仅勾选的图像或页面会发送；最多选择 200 张，仍受同一预算约束。首次运行前选择。":"当前按文字模型运行。图像可本地预览，模型看图需明确配置支持图像的 API 模型后新建任务。";
  $("documents").innerHTML=job.documents.map(doc=>'<p><strong>'+esc(doc.filename)+'</strong> · '+doc.page_count+' 页 / '+doc.block_count+' 个文字区域</p><ul>'+doc.warnings.map(w=>'<li>'+esc(w)+'</li>').join("")+'</ul>').join("");
  $("limitations").innerHTML=job.limitations.slice(0,100).map(text=>'<li>'+esc(text)+'</li>').join("");
  if(changed||revisionChanged)$("layout-original").innerHTML=job.documents.filter(d=>["pdf","docx"].includes(d.format)).map(d=>'<option value="'+d.id+'">'+esc(d.filename)+'</option>').join("");
  $("compare-layout").disabled=!$("layout-original").options.length||job.layouts.some(l=>["preparing",...activeStates].includes(l.state));
  Object.values(views).filter(visible).forEach(v=>guarded(()=>loadView(v.kind)));
  renderLayouts();
  window.AWTSubmission?.render(job);
  if(active||job.layouts.some(l=>["preparing",...activeStates].includes(l.state))||["running","cancel_requested"].includes(job.submission?.state))timer=setTimeout(poll,document.hidden?5000:1800);
}
async function poll(){const id=job?.id;try{const data=await post("/api/project/status",{job_id:id});if(job?.id===id)render(data);}catch(failure){error("进度读取失败；检查点仍保存在本机。"+failure.message);timer=setTimeout(poll,5000);}}
$("start").onclick=()=>guarded(async()=>render(await post("/api/project/start",{job_id:job.id,image_ids:[...selectedAssets],retry_uncertain:$("retry-uncertain").checked,max_calls:Number($("resume-calls").value),total_tokens:Number($("resume-tokens").value)})));
$("pause").onclick=()=>guarded(async()=>render(await post("/api/project/control",{job_id:job.id,action:"pause"})));
$("cancel").onclick=()=>guarded(async()=>render(await post("/api/project/control",{job_id:job.id,action:"cancel"})));
$("steer").onclick=()=>guarded(async()=>render(await post("/api/project/control",{job_id:job.id,action:"steer",goal:$("steering").value})));
$("revise").onclick=()=>guarded(async()=>{if(uploadBusy)return;uploadBusy=true;$("revise").disabled=true;try{const files=await uploads([...$("revision-files").files],$("revision-status"));$("revision-status").textContent="正在匹配未变内容和受影响的检查…";render(await post("/api/project/revise",{job_id:job.id,files}));$("revision-status").textContent="复查计划已保存；点击继续后执行未完成批次。";}finally{uploadBusy=false;$("revise").disabled=activeStates.includes(job?.state);}});
$("download").onclick=()=>guarded(async()=>{const data=await post("/api/project/status",{job_id:job.id,compact:false});const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),link=document.createElement("a");link.href=url;link.download="awt-project-review-"+job.id.slice(0,8)+".json";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});

$("compare-layout").onclick=()=>guarded(async()=>{
  const file=$("layout-revised").files[0];if(!file)throw new Error("请选择修改后的 PDF 或 DOCX");$("compare-layout").disabled=true;
  try{const revised=await upload(file,$("layout-status"));const data=await post("/api/project/layout",{job_id:job.id,document_id:$("layout-original").value,revised,background:true,page_start:Number($("layout-from").value),page_end:$("layout-to").value?Number($("layout-to").value):null});activeLayout=null;layoutPreview=null;render(data);$("layout-status").textContent="本地逐页处理中；可暂停，并保留已经完成的页。";}catch(failure){$("compare-layout").disabled=false;throw failure;}
});
function renderLayouts(){
  $("layout-results").hidden=!job.layouts.length;if(!job.layouts.length)return;
  if(!activeLayout||!job.layouts.some(l=>l.id===activeLayout)){activeLayout=job.layouts.at(-1).id;layoutPreview=null;}
  const report=job.layouts.find(l=>l.id===activeLayout),active=["preparing",...activeStates].includes(report.state);
  const layoutState={completed:"本地逐页渲染已完成",running:"正在逐页渲染",pause_requested:"当前页保存后暂停",cancel_requested:"当前页保存后取消"}[report.state]||states[report.state]||"已渲染";
  $("layout-version").innerHTML=job.layouts.map(l=>'<option value="'+l.id+'" '+(l.id===activeLayout?"selected":"")+'>'+esc(l.after_filename+" · "+l.created_at)+'</option>').join("");
  $("layout-summary").textContent=layoutState+" · "+report.before_pages+" → "+report.after_pages+" 页；已保存 "+report.rendered_count+" / "+report.planned_count+" 页；"+report.changed_count+" 页变化；人工检查 "+report.checked_count+" 页。"+(report.error||report.scope);
  $("layout-progress").max=Math.max(1,report.planned_count);$("layout-progress").value=report.rendered_count;
  $("pause-layout").disabled=!active;$("cancel-layout").disabled=["completed","cancelled"].includes(report.state);$("resume-layout").disabled=active||report.state==="completed";
  $("layout-page").min=report.page_start||1;$("layout-page").max=report.page_end||Math.max(report.before_pages,report.after_pages,1);
  if(Number($("layout-page").value)<Number($("layout-page").min)||Number($("layout-page").value)>Number($("layout-page").max))$("layout-page").value=$("layout-page").min;
  if(report.planned_count&&(!layoutPreview||!layoutPreview.rendered))guarded(()=>showLayoutPage());
}
async function showLayoutPage(){
  const id=job.id,layout=activeLayout,number=Number($("layout-page").value);
  const page=await post("/api/project/layout/page",{job_id:id,layout_id:layout,page:number});
  if(job?.id!==id||activeLayout!==layout||Number($("layout-page").value)!==number)return;
  layoutPreview=page;
  $("layout-page-status").textContent=page.rendered?(page.changed?"此页有像素变化":"此页无像素变化"):"此页尚未渲染";
  $("page-pair").innerHTML=["before","after"].map((side,index)=>'<figure><figcaption>'+(index?"修改后":"修改前")+" · 第 "+number+' 页</figcaption>'+(page[side].available?'<button class="secondary" data-enlarge-page>放大'+(index?"修改后":"修改前")+'页面</button><img alt="'+(index?"修改后":"修改前")+"第 "+number+' 页" src="data:'+page[side].mime_type+";base64,"+page[side].data_base64+'">':'<div class="empty-page">'+(page.rendered?"此版本没有对应页":"等待本页渲染")+'</div>')+'</figure>').join("");
  $("page-checked").checked=page.human_checked;$("page-checked").disabled=!page.rendered;$("save-layout-check").disabled=!page.rendered;
}
$("layout-version").onchange=()=>{activeLayout=$("layout-version").value;layoutPreview=null;renderLayouts();};
$("show-layout-page").onclick=()=>guarded(()=>showLayoutPage());
$("layout-page").onchange=()=>guarded(()=>showLayoutPage());
for(const [id,action] of [["pause-layout","pause"],["resume-layout","resume"],["cancel-layout","cancel"]])$(id).onclick=()=>guarded(async()=>render(await post("/api/project/layout/control",{job_id:job.id,layout_id:activeLayout,action})));
$("page-pair").onclick=event=>{const button=event.target.closest("[data-enlarge-page]");if(button){const image=button.parentElement.querySelector("img");$("preview-image").src=image.src;$("preview-label").textContent=image.alt;$("preview").showModal();}};
$("save-layout-check").onclick=()=>guarded(async()=>{if(!layoutPreview?.rendered)return;const checked=$("page-checked").checked;render(await post("/api/project/layout/check",{job_id:job.id,layout_id:activeLayout,page:Number($("layout-page").value),checked,after_sha256:layoutPreview.after_sha256}));layoutPreview.human_checked=checked;});
guarded(async()=>{const response=await fetch("/api/runtime"),data=await response.json();$("model").textContent=data.provider?modelLabel(data):"模型配置无效，请运行 awt --check";await loadJobs();const id=new URL(location.href).searchParams.get("job");if(id)render(await post("/api/project/status",{job_id:id}));});
