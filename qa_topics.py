"""Infer QA directions from this job's actual original questions."""
import json
from pathlib import Path
from judge import request_json
from semantic import read_api_key

PROMPT='''根据当前product及本次AI原问归纳提问方向，为后续分类和QA选题准备。只组织方向，不回答问题，不删改原问，不把原问当作买家真实数据或本品事实。
方向取决于这批原问，不预设固定的七八类。下游主QA以10条为目标，并需备选；原问支持时归纳约10—15个独立具体关注点供选题，不强拆同一方向凑数。合并同一关注点的近义方向，但不要用“功能”“其他”包办大量具体问题。清洁/保养若在原问中出现，可以独立成方向；没有相关原问时不要补造。属性限定、提问方向和关键词等级是不同维度。
输出JSON对象topics数组，每项为简短中文方向名。不要返回QA、等级或逐问映射。'''


def discover_topics(groups,product,model,path,transport=request_json,key_reader=read_api_key):
    questions=[{'id':g['group_id'],'text':g['text']} for g in groups if g['kind']=='ai_generated_question']
    payload={'product':product,'questions':questions};path=Path(path)
    if path.exists():
        saved=json.loads(path.read_text(encoding='utf-8'))
        if saved.get('input')==payload and saved.get('model')==model and saved.get('prompt')==PROMPT:return saved['topics']
    if questions:
        result,usage=transport([payload],model,key_reader(),PROMPT)
        topics=list(dict.fromkeys(t.strip() for t in result.get('topics',[]) if isinstance(t,str) and t.strip() and t.strip()!='其他'))
    else:result={};usage={};topics=[]
    topics.append('其他')
    path.write_text(json.dumps({'input':payload,'model':model,'prompt':PROMPT,'response':result,'usage':usage,'topics':topics},ensure_ascii=False,indent=2),encoding='utf-8')
    return topics
