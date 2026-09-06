"use strict";
window.AWTSubmission=(()=>{
  const labels={block:"阻断问题",warning:"警告",manual:"需人工核对",unchecked:"尚未检查",pass:"规则检查通过",recorded:"已记录人工核对"};
  const runStates={idle:"可开始本地校验",running:"正在本地校验",cancel_requested:"正在停止",cancelled:"已取消，可重新运行",interrupted:"上次校验中断，可重新运行",failed:"校验未完成",completed:"报告已保存"};
  const textFields=["target","requirements_source"],choiceFields=["kind","count_unit","citation_mode"];
  const numberFields=["max_words","max_abstract_words","max_pages","max_figures","max_tables","page_width_mm","page_height_mm","min_image_dpi"];
  const flags=["requirements_confirmed","embedded_fonts","anonymous","require_model_review","require_layout"];
  const lists=["declarations","required_files","anonymous_terms"];
  const id=key=>"sub-"+key.replaceAll("_","-");
  let current=null,settings=null,dirty=false,report=null,reportId=null,offset=0,total=0,signature="",busy=false,loading=false,again=false,editingItem=null,pendingReportRun=false;
  async function guarded(action){
    $("sub-error").hidden=true;$("sub-confirm-error").hidden=true;
    try{await action();}catch(failure){const message=$("sub-confirm-dialog").open?$("sub-confirm-error"):$("sub-error");message.textContent=failure.message||"校验操作未完成，请重试。";message.hidden=false;}
  }
  function lines(text){return text.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);}
  async function call(action,data={}){return post("/api/project/submission/"+action,{job_id:current.id,...data});}
  function changed(value){dirty=value;$("sub-dirty").textContent=value?"表单有未保存修改；已有报告仍对应之前保存的规则。":"规则已载入。";if(report)drawReport(report);}
  function populate(profile){
    [...textFields,...choiceFields].forEach(key=>$(id(key)).value=profile[key]);
    numberFields.forEach(key=>$(id(key)).value=profile[key]??"");flags.forEach(key=>$(id(key)).checked=profile[key]);lists.forEach(key=>$(id(key)).value=profile[key].join("\n"));
    $("sub-outline").value=profile.outline.map(row=>[row.heading,row.task,row.keywords.join("；")].join(" | ").replace(/(?:\s*\|\s*)+$/,"")).join("\n");
    $("sub-files").innerHTML='<table><thead><tr><th>当前材料</th><th>本轮角色</th></tr></thead><tbody>'+current.documents.map(d=>'<tr><td>'+esc(d.filename)+'</td><td><select aria-label="'+esc(d.filename)+' 的投稿角色" data-sub-file="'+esc(d.filename)+'">'+Object.entries({manuscript:"正文（参与计数和匿名扫描）",references:"参考文献",attachment:"附件（只记录文件完整性）",exclude:"不纳入本轮"}).map(([value,label])=>'<option value="'+value+'" '+(profile.files[d.filename]===value?'selected':'')+'>'+label+'</option>').join("")+'</select></td></tr>').join("")+'</tbody></table>';
    changed(false);
  }
  function profile(){
    const value={};[...textFields,...choiceFields].forEach(key=>value[key]=$(id(key)).value);
    numberFields.forEach(key=>value[key]=$(id(key)).value===""?null:Number($(id(key)).value));
    flags.forEach(key=>value[key]=$(id(key)).checked);lists.forEach(key=>value[key]=lines($(id(key)).value));
    value.files=Object.fromEntries([...$("sub-files").querySelectorAll("[data-sub-file]")].map(select=>[select.dataset.subFile,select.value]));
    value.outline=lines($("sub-outline").value).map(line=>{const parts=line.split("|");if(parts.length>3)throw new Error("每行大纲最多包含标题、任务和关键词三部分");return {heading:parts[0].trim().replace(/^(?:#+|[-*])\s+/,""),task:(parts[1]||"").trim(),keywords:(parts[2]||"").split(/[;；]/).map(s=>s.trim()).filter(Boolean)};});
    return value;
  }
  async function refreshSettings(force=false){
    const identifier=current.id,data=await call("status");if(current?.id!==identifier)return;
    settings=data;if(force||!dirty)populate(data.profile);drawState(data);
  }
  function drawState(value){
    const running=["running","cancel_requested"].includes(value.state);
    $("sub-progress").textContent=(runStates[value.state]||value.state)+" · "+(value.error||value.progress||"不调用模型");
    $("sub-run").disabled=busy||running||["running","pause_requested","cancel_requested"].includes(current.state)||current.layouts.some(r=>["running","preparing","pause_requested","cancel_requested"].includes(r.state));
    $("sub-cancel").disabled=value.state!=="running";$("sub-save").disabled=busy||running;$("sub-reload").disabled=running;
    $("sub-rules").querySelectorAll("input,select,textarea").forEach(element=>element.disabled=running);
    const versions=value.reports||[];$("sub-report").hidden=!versions.length;
    if(pendingReportRun&&!running){
      if(value.state==="completed"&&versions.length){reportId=versions[0].id;offset=0;signature="";}
      pendingReportRun=false;
    }
    if(!versions.length)return;
    if(!reportId||!versions.some(r=>r.id===reportId)){reportId=versions[0].id;offset=0;signature="";}
    $("sub-report-version").innerHTML=versions.map(r=>'<option value="'+r.id+'" '+(r.id===reportId?'selected':'')+'>'+esc(r.created_at)+(r.stale?" · 已过期":"")+'</option>').join("");
    const selected=versions.find(r=>r.id===reportId),next=JSON.stringify([current.id,reportId,selected.stale,value.profile_sha256,current.revision,value.confirmation_revision]);
    if(next!==signature){signature=next;guarded(loadReport);}
  }
  function drawReport(data){
    report=data;
    const stale=data.stale;
    $("sub-stale").textContent=stale?"这份报告已过期：文件、规则、审阅或排版记录发生了变化。请重新校验后处理当前稿件。":dirty?"规则表单有未保存修改。当前报告对应已保存规则；请保存并重新校验后记录人工结果。":data.state==="blocked"?"存在阻断问题，请先处理对应材料或规则。":data.state==="needs_review"?"本地检查已完成，仍有警告、人工核对或尚未检查的项目。":"当前清单已完成；请由作者决定最终提交。";
    $("sub-counts").innerHTML=Object.entries(labels).map(([status,label])=>'<div class="sub-count"><strong>'+data.counts[status]+'</strong>'+label+'</div>').join("");
    $("sub-metrics").textContent="正文提取统计 "+data.metrics.text_count.toLocaleString()+" · 摘要 "+data.metrics.abstract_count+" · PDF "+data.metrics.pdf_pages+" 页 · 识别图号 "+data.metrics.figure+" / 表号 "+data.metrics.table+" · 模型调用 0"+(data.omitted_items?" · 另有 "+data.omitted_items+" 条未展开，请分章缩小范围":"");
    $("sub-items").innerHTML=data.items.length?data.items.map(item=>'<article class="claim sub-'+item.status+'"><div class="bar"><strong>'+esc(item.title)+'</strong><span class="badge">'+labels[item.status]+'</span></div><p>'+esc(item.detail)+'</p>'+item.anchors.map(a=>'<p>'+(a.locator?'<button class="secondary" data-sub-locator="'+esc(a.locator)+'" '+(stale?'disabled':'')+'>'+esc(a.filename+" · "+a.location)+'</button>':esc(a.filename+" · "+a.location))+'</p>'+(a.quote?'<div class="quote">'+esc(a.quote)+'</div>':'')).join("")+(item.confirmation?'<p class="stat">'+esc(item.confirmation.reviewer+" · "+item.confirmation.at+" · "+item.confirmation.note)+'</p>':'')+(['warning','manual','recorded'].includes(item.status)?'<button class="secondary" data-sub-confirm="'+item.id+'" '+(stale||dirty?'disabled':'')+'>记录人工处理</button>':'')+'</article>').join(""):'<p class="empty">当前筛选没有记录。</p>';
    total=data.total;$("sub-page-count").textContent=(total?offset+1:0)+"–"+Math.min(offset+20,total)+" / "+total;$("sub-prev").disabled=offset===0;$("sub-next").disabled=offset+20>=total;
    $("sub-manifest").innerHTML='<table><thead><tr><th>文件</th><th>角色</th><th>SHA-256</th></tr></thead><tbody>'+data.source_manifest.map(s=>'<tr><td>'+esc(s.filename)+'</td><td>'+esc({manuscript:"正文",references:"参考文献",attachment:"附件"}[s.role])+'</td><td>'+s.sha256+'</td></tr>').join("")+'</tbody></table>';
    $("sub-report-hash").textContent="报告 SHA-256："+data.report_sha256;
  }
  async function loadReport(){
    if(!reportId)return;if(loading){again=true;return;}loading=true;
    const identifier=current.id,selected=reportId,position=offset,filter=$("sub-filter").value;
    try{const data=await call("report",{report_id:selected,offset:position,limit:20,status:filter});
      if(current?.id!==identifier||reportId!==selected||offset!==position||$("sub-filter").value!==filter){again=true;return;}
      if(position&&position>=data.total){offset=0;again=true;return;}drawReport(data);
    }finally{loading=false;if(again){again=false;guarded(loadReport);}}
  }
  function renderJob(value){
    const changedJob=!current||current.id!==value.id;current=value;$("submission-panel").hidden=false;
    if(changedJob){settings=null;dirty=false;report=null;reportId=null;offset=0;signature="";pendingReportRun=false;$("sub-filter").value="all";guarded(()=>refreshSettings(true));}
    else if(value.submission){drawState(value.submission);if(settings&&settings.profile_sha256!==value.submission.profile_sha256&&!dirty)guarded(()=>refreshSettings());}
  }
  $("sub-rules").addEventListener("input",()=>changed(true));$("sub-rules").addEventListener("change",()=>changed(true));
  $("sub-reload").onclick=()=>guarded(()=>refreshSettings(true));
  $("sub-save").onclick=()=>guarded(async()=>{settings=await call("configure",{profile:profile()});populate(settings.profile);signature="";drawState(settings);});
  $("sub-run").onclick=()=>guarded(async()=>{
    if(busy)return;busy=true;$("sub-run").disabled=true;
    try{settings=await call("run",{profile:profile()});populate(settings.profile);pendingReportRun=true;signature="";$("sub-filter").value="all";drawState(settings);render(await post("/api/project/status",{job_id:current.id}));}
    finally{busy=false;if(current?.submission)drawState(current.submission);}
  });
  $("sub-cancel").onclick=()=>guarded(async()=>{drawState(await call("cancel"));render(await post("/api/project/status",{job_id:current.id}));});
  $("sub-report-version").onchange=()=>{reportId=$("sub-report-version").value;pendingReportRun=false;offset=0;signature="";guarded(loadReport);};
  $("sub-filter").onchange=()=>{offset=0;guarded(loadReport);};
  $("sub-prev").onclick=()=>{offset=Math.max(0,offset-20);guarded(loadReport);};$("sub-next").onclick=()=>{offset+=20;guarded(loadReport);};
  $("sub-items").onclick=event=>{const button=event.target.closest("button");if(!button)return;
    if(button.dataset.subLocator)guarded(()=>showSource(button.dataset.subLocator));
    if(button.dataset.subConfirm){editingItem=report.items.find(i=>i.id===button.dataset.subConfirm);$("sub-confirm-title").textContent=editingItem.title;$("sub-note").value=editingItem.confirmation?.note||"";$("sub-decision").value="checked";$("sub-confirm-dialog").showModal();}
  };
  $("sub-confirm-close").onclick=()=>$("sub-confirm-dialog").close();
  $("sub-confirm-save").onclick=()=>guarded(async()=>{await call("confirm",{report_id:report.id,item_id:editingItem.id,binding:report.binding,reviewer:$("sub-reviewer").value,note:$("sub-note").value,decision:$("sub-decision").value});$("sub-confirm-dialog").close();await loadReport();});
  for(const format of ["json","markdown"]){$("sub-"+format).onclick=()=>guarded(async()=>{const data=await call("export",{report_id:reportId,format}),content=format==="json"?JSON.stringify(data,null,2):data.content;const url=URL.createObjectURL(new Blob([content],{type:format==="json"?"application/json":"text/markdown;charset=utf-8"})),link=document.createElement("a");link.href=url;link.download=format==="json"?"awt-submission-"+reportId.slice(0,8)+".json":data.filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});}
  return {render:renderJob};
})();
if(typeof job!=="undefined"&&job)window.AWTSubmission.render(job);
