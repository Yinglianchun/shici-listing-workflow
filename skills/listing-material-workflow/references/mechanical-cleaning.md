# 可选机械清洗脚本

用户使用的AI环境支持代码运行时，由当前agent在该环境运行scripts/clean_materials.py.txt；不要求用户电脑安装Python，不需要API Key或第三方包。文件是Python源码，保留.txt后缀便于传递，直接交给Python解释器即可。无代码环境时用文件工具完成相同规则，不声称脚本已执行。

脚本只做规范化、women/womens/所有格统一比较、确定性重复去重、关键词词序去重、字面排序、已确认品牌词移除及广告A列逗号/单引号处理。不提炼问句关键表达，不做本品适用性、属性分级、同义/完整包含判断、选QA或写描述，也不调用其他LLM。字面排序不是语义分组；问句不按词袋删除，新增属性、否定、数值和条件继续保留。agent仍需对相似候选按方向与条件判断，但无需人工两两比对全量词池。

输入为CSV或JSON行对象数组，必须有Keyword；Type或kind区分keyword和question，无法确认的标unknown，不按词序合并。跨Sheet输入加sheet字段，避免把不同表页互相删除；来源或其他列放同一行对象即可保留。Excel用环境表格工具读取为行对象，不把原文或来源字段改成清洗值。

当前只做01时使用：
`python scripts/clean_materials.py.txt --mode dedup --input 输入.csv --output 过程记录/基础清洗.json`

当前只做06且agent已提炼关键表达后使用：
`python scripts/clean_materials.py.txt --mode ad-a --input 广告A列及原文.json --output 过程记录/广告A列清理.json`

03筛选前可先用去品牌模式，只移除brands.json所列他牌，原文及其他属性留档，之后由agent筛剩余表达：
`python scripts/clean_materials.py.txt --mode strip-brands --brands brands.json --input 输入.csv --output 过程记录/去品牌待筛.json`
brands.json为品牌字符串数组，不能包含自有品牌。此模式不会自动判断剩余表达适用；竞品型号或缺失比较对象仍需agent核对。

ad-a不会将完整问题自动变成关键词。它只清理输入Keyword字段并保留其他字段，按清理结果去重。普通分隔逗号换空格、单引号删除；英文千位分隔转为原数值，其他数字逗号含义不明时进入pending，先问清或由agent核对，不丢弃、不擅改尺寸。否定缩写先展开。

读取records中的row更新当前步骤Excel，originals和source_rows留过程文件供追溯，pending交由当前agent判断/追问。JSON是辅助结果，不代替每阶段的真实Excel交付；使用用户已有模板和样式，保留完整原问及原始来源。完成当前一步并保存后停下，不借脚本连跑后续。
