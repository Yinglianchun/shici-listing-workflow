"""Save a portable, stage-specific handoff beside each project's completed files."""
import json
import shutil
from collections import Counter
from pathlib import Path
from naming import named_file

LEGACY_NAMES=['导入与基础去重','属性分级','独立QA选题','语义关系整理','本品适用性筛选','归并与短语清洗','合并前本品自查','前缀合并与广告词','描述组合与导出']
LEGACY_INPUTS={1:[],2:[1],3:[1,2],4:[1],5:[1],6:[1,2,3,4,5],7:[6],8:[7],9:[8]}
LEGACY_TASKS={
1:'导入input中的CSV，保留全部来源与原文，做基础规范化去重；不做语义合并。',
2:'分别给关键词和完整问句重新计算独立限定数，按等级分Sheet。清洁等提问方向单列，不加等级；钓鱼与高尔夫分别算两个限定。',
3:'从未语义合并的完整原问独立选QA，按7—8个方向组织选题，每方向只选一个具体问题并全面回答，关联能被同一答案实际覆盖的原问。只依据本品资料写双语QA与A+，英文回答分别最多250和500字符。',
4:'判断同义、部分重合、仅同主题等关系，保留双方独有条件。语义相似只是候选，不直接删除；没有embedding也可以用LLM逐组比较。',
5:'逐条对照本品资料，分可用、不适用、待补资料、仅某已确认子体适用，保留依据和原文。资料缺失不等于商品没有。',
6:'结合关系与适用性结果归并同义素材，保留新词和独有条件；保留完整问句并另列清洗短语，关键词、问句和短语按等级分Sheet。此时不要拼成整段。',
7:'重新独立对照最新本品完整详情，逐条核对分好级的完整原文及清洗表达，尤其检查丢失条件与混入的竞品功能；不能照抄05结论。',
8:'只使用07通过及人工确认可用的素材，按完整单词边界合并高度重合前缀；广告关键词另存完整独立的一词一行CSV，不能只保留后缀。0级、1级关键词和问句标建议否定，但不影响QA与描述用途；另存完整否定候选（低等级可用素材及明确不符关键词），附原因和依据，匹配方式待选择。待确认不自动转否定，不拆成宽泛单词，不自动操作广告账户。',
9:'按现有素材自然组合描述，不凑字数、不截断单条；用分号连接成一段，不含内容换行；描述稿列宽和显示高度自适应；另存采用明细和TXT，记录实际字符数。'}


STAGE_NAMES=['导入与基础去重','相似素材排序分组','本品适用性筛选','高重合素材去重','方向分类与属性分级','独立QA选题与回答','短语清洗与本品复核','前缀整理与广告词','描述组合与导出']
NEW_STAGE_NAMES=[*STAGE_NAMES[:2],STAGE_NAMES[3],STAGE_NAMES[2],*STAGE_NAMES[4:]]
INPUT_STAGES={1:[],2:[1],3:[1,2],4:[1,2,3],5:[1,3,4],6:[1,3,4,5],7:[1,3,4,5,6],8:[7],9:[8]}
TASKS={
1:LEGACY_TASKS[1],
2:'仅用文字重合度、embedding和程序排序分组，保留全部原文及来源；没有embedding时可按文字重合度排序并标明缺少语义评分，不用LLM冒充embedding。分组仅为比较候选，不删除、不沿相似链直接归并。',
3:LEGACY_TASKS[5]+'明确不符退出后续处理，待补资料的问句保留到QA备用池。',
4:'对筛选后留下的高文字重合或高语义相似候选判断是否重复。只有方向、条件与有效用词都重复才归入代表；新方向、新词、否定、数值、用途和独有条件均保留。保存原文到代表的映射与全部变体，不销毁原问。',
5:LEGACY_TASKS[2]+'关键词直接填写所读Skill的assets/关键词分级空模板.xlsx的五张等级Sheet，不加总览，属性明细写可读短语，不放JSON。问句分级和原文映射另存明细表。只给去重后的代表分级，完全重复变体继承代表方向和等级；问句的待补资料标记继续保留。',
6:LEGACY_TASKS[3]+'必须读取01的完整原问与04全部变体，结合03状态和05方向，不只看代表；待补资料问句可选题但不编答案。',
7:'对可用素材生成独立清洗短语，按等级分别保存关键词、完整问句和短语；保留新词与原问变体，不再把第04步保留的差异合没。清洗后重新对照本品完整详情，记录是否丢条件或混入功能，不能照抄03结论。',
8:LEGACY_TASKS[8],9:LEGACY_TASKS[9]}

def write_handoff(folder):
    folder=Path(folder).resolve()
    cfg=json.loads((folder/'job.json').read_text(encoding='utf-8'))
    single=cfg.get('report_mode')=='single-workbook'
    product_file=named_file(folder,'素材总表.xlsx' if single else '00_本品资料.xlsx').relative_to(folder).as_posix()
    qa_file=named_file(folder,'QA与A+问答.xlsx').relative_to(folder).as_posix()
    ad_file=named_file(folder,'08_广告关键词.csv' if cfg.get('export_prefix') else '广告关键词.csv').name
    description_file=named_file(folder,'商品描述素材.docx' if single else '09_商品描述素材草稿.txt' if cfg.get('export_prefix') else '商品描述素材草稿.txt').name
    status=json.loads((folder/'status.json').read_text(encoding='utf-8'))
    modern=cfg.get('workflow') in ('sorted-first','dedup-first')
    new_order=cfg.get('workflow')=='dedup-first'
    names=NEW_STAGE_NAMES if new_order else STAGE_NAMES if modern else LEGACY_NAMES
    inputs=INPUT_STAGES if modern else LEGACY_INPUTS
    tasks=TASKS if modern else LEGACY_TASKS
    if new_order:
        tasks={**TASKS,3:'只依据原始A列Keyword文本判断重复，不读旧Level/CoreTerm/Modifiers/Intent/Evidence；Type只用于分流，原文ID用于返回保留/删除映射，后续再重新整理与分级。按完整相似组去重，重复表达只留一条。通用规则：同一提问方向下，X问题完整包含Y问题的全部信息时，保留X、剔除Y；各有独有信息都保留。不改写或合并问题，不因同主题或共用答案删除。广告关键词新增限定继续保留。300条是装批目标，不能切断相似组；原文留在来源记录。',4:LEGACY_TASKS[5]+'只筛03留下的素材；剔除原问仍供独立QA参考，未单独筛选的原问标待确认。',6:LEGACY_TASKS[3]+'读取01完整原问与03删除映射，结合04适用性和05方向；问题完整包含关系不能直接沿用较长问题的属性等级。',7:TASKS[7].replace('第04步','第03步').replace('03结论','04结论')}
    if single:
        tasks={**tasks,
            5:'根据本次完整原问归纳提问方向，不固定分类数量；关键词和问句分别重新按独立语义限定分级，更新总表的0-1、2、3、4级及以上分表。当前属性、核心词和方向重新判断，旧Level、Evidence仅供追溯。此时问句A列留空，完整原问另列。',
            6:'读取01完整原问与03删除映射，结合04适用性及05方向；从实际方向中选约10条主QA，每方向一个问题，另留备选；清洁可独立成类。主QA英文尽量240—250字符，A+另选2—3条尽量480—500字符，分别不得超过250/500，中文译文另列。依据不足可以短些，不造内容凑数。输出独立QA与A+问答.xlsx，含主QA、备选QA、备选原问及少量A+，原文与关联保留。',
            7:'清洗问句的提问结构、助动词、普通介词和代商品代词，保留否定、数值及必要关系。清洗后重新对照完整本品，排除不可用项，更新总表等级页；不另出复核表。广告词保留完整，QA用过的问句也不能绕过清洗。',
            8:'更新总表广告和否定候选：0/1级为精准否定候选；固定词组单列已确认，模型建议另标。待确认不自动转否定，small、polarized依本品与已确认子体判断。完整广告词保留，共同前缀仅压缩描述，不另交CSV。',
            9:'用最终可用的清洗短语组合描述，分号连接一段，不凑字数、不截断完整素材，遵守本次字符上限。总表记录长度，另存真实Word，最终交素材总表Excel、独立QA问答Excel和Word描述素材三个文件，过程文件保留。'}
    completed=[]
    for i,step in enumerate(status['steps'],1):
        if step['state']!='done':break
        completed.append(i)
    next_stage=len(completed)+1
    skill=folder/'使用的Skill/listing-material-workflow'
    source=Path(__file__).parent/'skills/listing-material-workflow'
    excluded={'03_本品适用性筛选.xlsx','04_高重合素材去重.xlsx'} if new_order else {'03_高重合素材去重.xlsx','04_本品适用性筛选.xlsx'}
    files=['SKILL.md','references/stages.md','references/templates.md','references/product-analysis.md','references/stage-files-legacy.md']+[p.relative_to(source).as_posix() for p in sorted((source/'assets').glob('*.xlsx')) if (p.name in ('素材总表空模板.xlsx','QA与A+问答空模板.xlsx') if single else p.name not in excluded)]
    for name in files:
        target=skill/name;target.parent.mkdir(parents=True,exist_ok=True)
        source_name=name
        if name=='references/stages.md' and not new_order:source_name='references/sorted-stages.md' if modern else 'references/legacy-stages.md'
        if name=='SKILL.md' and modern and not new_order:source_name='references/sorted-workflow.md'
        shutil.copyfile(source/source_name,target)
        if name=='references/templates.md' and not new_order:
            text=target.read_text(encoding='utf-8').replace('03_高重合素材去重','04_高重合素材去重').replace('04_本品适用性筛选','03_本品适用性筛选')
            target.write_text(text,encoding='utf-8')
    product=cfg['product']
    analysis_file=folder/'product_analysis.json'
    if analysis_file.exists():
        saved=json.loads(analysis_file.read_text(encoding='utf-8'))
        if saved.get('product')==product:product={**product,'analysis':saved['analysis']}
    (folder/'product.json').write_text(json.dumps(product,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['请使用 listing-material-workflow skill 接着整理这个项目。',f'项目文件夹：{folder}',
        '请直接由你阅读、判断并完成指定阶段，不启动本地工作台、不运行工作流脚本、不调用外部LLM API代跑，也不要求用户安装Python或提供API Key。可用文件/表格工具辅助读写、基础统计与导出Excel；语义分析和内容判断由你自己执行。',
        '如果文件夹换了电脑或位置，以你实际打开的项目文件夹为准，下面文件名均相对该文件夹。',
        '先读取：使用的Skill/listing-material-workflow/SKILL.md，再读 references/stages.md（相对该Skill）。',
        f'然后读取：product.json（完整本品详情与待确认事项）、{product_file}。',
        '若“人工续做/续做记录.md”已存在，先读它及记录指向的新产物；以下进度只代表程序结果，已人工完成的阶段不要重做，改为继续记录中的下一阶段。']
    if analysis_file.exists():
        lines.append('先读 product_analysis.json 的本品定位、卖点、原文依据、资料差异和待补项，再核对完整资料；分析不覆盖原文或用户已确认决定。')
        analysis_table=named_file(folder,'素材总表.xlsx' if single else '00_本品分析.xlsx')
        if analysis_table.exists():lines.append('本品分析表：'+analysis_table.relative_to(folder).as_posix())
    elif new_order:
        lines.append('进入AI去重、筛选或选QA前，先按Skill补做00本品分析：提炼定位、卖点、人群和场景；冲突引用两段原文，缺失资料单列。将Excel保存到人工续做/表格，保留完整原文；已知部分可继续，不把缺资料当成商品没有。')
    app_file=folder/('stage4.json' if new_order else 'stage3.json')
    dedup_file=folder/('stage3.json' if new_order else 'stage4.json')
    if modern and app_file.exists() and dedup_file.exists():
        app=json.loads(app_file.read_text(encoding='utf-8'))
        dedup=json.loads(dedup_file.read_text(encoding='utf-8'))
        kept=set(dedup.get('kept_ids',[]));groups={g['group_id']:g for g in dedup.get('groups',[])}
        eligible=[i for i in kept if app.get(i,{}).get('status')=='eligible']
        pending=[i for i in kept if app.get(i,{}).get('status')=='pending']
        kinds=Counter(groups.get(i,{}).get('kind','unknown') for i in eligible)
        deleted_pending=[i for i,r in app.items() if i not in kept and r.get('status')=='pending']
        lines.append(f'筛选交接：可用代表{len(eligible)}条（关键词{kinds["keyword"]}、问句{kinds["ai_generated_question"]}）；待确认代表{len(pending)}条；另有{len(deleted_pending)}条去重剔除但留档的待确认原文，不能把它们重复计入待确认代表。')
        lines.append(f'适用性Excel只列可用代表，未列出的内容不等于已丢失。读取{app_file.name}的状态及原因、{dedup_file.name}的保留映射，再读stage1.json完整原文；待确认问句仍可选QA，但不得编写肯定答案，待确认素材不进入正式广告和描述。')
    done_files=list(dict.fromkeys(s['file'] for s in status['steps'] if s['state']=='done' and s.get('file')))
    lines.append('已完成：'+('、'.join(done_files) if done_files else '暂无完整阶段；原始CSV已保存在input。'))
    if next_stage<=9:
        lines.append(f'下一步只做 {next_stage:02d} {names[next_stage-1]}，完成后先停下。')
        dependencies=inputs[next_stage]
        required=list(dict.fromkeys(status['steps'][i-1]['file'] for i in dependencies if status['steps'][i-1].get('file')))
        question_details=named_file(folder,'05_问句与分级明细.xlsx')
        if next_stage>=6 and question_details.exists():required.append(question_details.relative_to(folder).as_posix())
        lines.append('本阶段接着读取：'+('、'.join(required) if required else 'input文件夹内的原始CSV。'))
        lines.append('需要完整来源或表格中较长内容时，可对应读取stageN.json；不要只依赖聊天中的摘要。')
        if (folder/'review_decisions.json').exists():lines.append('同时读取 review_decisions.json，保留人工修改及模型原建议。')
        lines.append('具体任务：'+tasks[next_stage])
        if single:lines.append('本项目采用总表模式：使用assets/素材总表空模板.xlsx的分表和列结构，每完成一个阶段就回填同一份总表，不新建阶段Excel。A列Keyword按本项目清洗规则生成，完整原问另列，旧等级与Evidence只作来源记录，不作为去重/分级依据。QA方向按这批原问归纳，清洁可独立成类；0/1级为精准否定候选，词组否定按本品与子体提出，不照搬其他款的small或polarized。')
        if single and next_stage>=6:lines.append(f'独立QA表：人工续做/表格/{Path(qa_file).name}；使用assets/QA与A+问答空模板.xlsx，主QA目标10条加备选和2—3条A+。不把QA重复塞回素材总表。')
        if next_stage==9:lines.append(f'本次描述字符上限：{cfg["max_characters"]}，不是要凑满的目标。')
        output_name=named_file(folder,'素材总表.xlsx' if single else f'{next_stage:02d}_{names[next_stage-1]}.xlsx').name
        lines.append(f'将真实Excel保存到本项目文件夹的“人工续做/表格/{output_name}”，保留程序原产物。' if single else f'将真实Excel保存到本项目文件夹的“人工续做/表格/{output_name}”，辅助CSV/TXT放在人工续做目录，保留程序原产物。')
        lines.append('每阶段实际更新保存同一份Excel，保留模板分表、标题和表头位置，不冻结；正文14或28，保留完整原问与来源。' if single else '每阶段必须实际保存Excel：第1行直接表头，不冻结，表头行高16.5、正文默认14，需要两行时28，按随附模板使用蓝底白字表头、宋体正文、灰白隔行和紧凑列宽；保留原文ID和来源。')
        if single and next_stage==9:lines.append(f'将分号连接的描述整理成真实Word：人工续做/{description_file}，9000按英文字符上限处理，不强行填满。最终交素材总表Excel、独立QA问答Excel和Word三个文件，过程JSON留在项目内。')
        lines.append('完成后更新“人工续做/续做记录.md”：本次完成阶段、产物路径、待补问题、下一阶段、先读哪些文件，并给出下一步可复制提示词。后续优先使用人工续做里的新产物，不重复旧阶段。')
    else:
        lines.append(f'程序阶段已完成。最终交付：{product_file}、{qa_file}、{description_file}；如需人工修改，在人工续做目录继续更新三个文件，过程文件保留。' if single else f'00—09程序阶段已完成。接下来核对07自查、{ad_file}和{description_file}；需要人工修改时另存“人工续做”，保留来源与修改理由，不自动发布。')
    lines.append('关键词、AI生成问句和中间结果不是官方资料或真实买家提问。不能拿竞品属性补本品卖点。')
    prompt='\n\n'.join(lines)+'\n'
    target=named_file(folder,'接下来怎么做.txt');target.write_text(prompt,encoding='utf-8')
    return {'folder':str(folder),'file':target.name,'completed':completed,'next_stage':next_stage if next_stage<=9 else None,'prompt':prompt}
