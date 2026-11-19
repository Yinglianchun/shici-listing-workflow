# 初步机械清洗脚本

01之前：先选本轮各版本CSV，运行core-terms模式抽取CoreTerm/Category候选，再由agent预填集中确认表单，问核心泛词是否需要补充。此模式不要求Keyword字段、不改原文、不推断全部Keyword都是核心。

`python scripts/clean_materials.py.txt --mode core-terms --input 各版本素材.json --output .tmp-listing/核心候选.json`

第01步：用户使用的AI环境支持代码运行时，默认由当前agent在该环境运行scripts/clean_materials.py.txt；不要求用户电脑安装Python，不需要API Key或第三方包。文件是Python源码，保留.txt后缀便于传递，直接交给Python解释器即可。无代码环境时用文件工具完成相同规则，不声称脚本已执行。

脚本只合并规范化后完全重复：统一大小写、空格、全半角、已约定末尾标点及women/womens/所有格比较写法，原文保留。关键词、问句都不按拆词排序判重；red frame blue lenses与blue frame red lenses必须分开。顺序不同、属性/部件归属不同、否定、数值或条件不同都不机械删除。

同顺序、整词连续完整包含仅写containment_candidates，记录short_id/long_id、双方文本及pending_applicability状态；id对应records的original_order，即输入行序号。双方仍保留在records，不因包含链间接删除，也不把sun当作sunglasses中的完整词。候选只在相同sheet、站点和素材类型中比较。确认03本品适用性后，04再判断是否真的可删；广告关键词增加限定仍分别保留，不用长词替代短词。

脚本还可字面排序、移除已确认品牌及清理广告A列标点；不提炼关键表达，不判断本品适用性、属性级别、同义覆盖或选QA写描述，也不调用其他LLM。字面排序及包含候选都不是语义结论。

输入为CSV或JSON行对象数组，必须有Keyword；Type或kind区分keyword和question，无法确认的标unknown，不按词序合并。跨Sheet输入加sheet字段，避免把不同表页互相删除；来源或其他列放同一行对象即可保留。Excel用环境表格工具读取为行对象，不把原文或来源字段改成清洗值。

## 年度用户搜索词报告

分级前导入，不等最后才拼表。00集中确认产品、报告时间范围；01先用sales-terms模式机械整理，再并入拓词池，接02排序、03适用性、04保守去重、05核心汇总与06分级。若项目已经完成分级，只对新增报告做同样整理、核对和分级后更新总表，不仅按词长塞进已有等级，也不重跑无关QA或描述。

用户这类导出只保留“用户搜索词”“订单数”两列，不要求额外销售额列。按用户确认的此类导出格式，保留表头，默认直接删除表头后的第一条数据行（总订单汇总行），不依赖其文字识别。若输入已经手动删过该行，调用时加--keep-first-row，避免误删第一条真实搜索词。脚本也移除第一列值为“总订单数/合计/总计/Grand Total”等的汇总行、空搜索词、0订单行，以及整格为B开头10位字母数字且含数字的ASIN行（忽略大小写）。不按B开头就删普通单词，不删除仅包含ASIN的完整搜索短语。只保留订单数明确大于0的行，订单数缺失或不明确时不猜成0，留给agent在本轮集中核对。

`python scripts/clean_materials.py.txt --mode sales-terms --input 年度搜索词.csv --output .tmp-listing/年度出单词.json`

若原列名不同，先读表头，再用`--term-column "实际搜索词列名" --orders-column "实际订单列名"`映射。Excel先用环境表格工具转CSV或行对象JSON，不要求用户电脑装Python。terms只包含两列的整理结果；records可直接进入后续流程，原词变体保留在originals中，Type标为keyword。

同一份完整年度导出中，按大小写、空格及women/womens/所有格规范化合并确定性重复，累计订单数，按订单数降序；不做语义去重、不把近义场景强行合并。不同产品、不同报告或重叠时间窗分开执行，不把重复导出直接叠加订单。与AI拓词合并时保留订单依据，但不给AI拓词编造订单。随后移除竞品品牌时，订单始终属于原始搜索词，不能把“miu miu sunglasses”订单冒充为去品牌后的“sunglasses”自然出单。

若提供的是有销售额而没有订单数的另一类报告，按实际字段筛销售额大于0并保留指标，不伪造订单数，也不调用sales-terms强猜列。此脚本不自行判断哪个出单词适用、值得投或应否定。

当前只做01时使用：
`python scripts/clean_materials.py.txt --mode dedup --input 输入.csv --output .tmp-listing/基础清洗.json`

第02步承接01输出：读取基础清洗.json中的records，row为保留文本，originals及source_rows为来源映射；结合containment_candidates和字面顺序组织比较候选。无需重复dedup；脚本不提供embedding，不据字面排序或包含关系删除语义近似项。完成02保存临时JSON，继续第二块的03，不额外交付阶段Excel。

当前只做06且agent已提炼关键表达后使用：
`python scripts/clean_materials.py.txt --mode ad-a --input 广告A列及原文.json --output .tmp-listing/广告A列清理.json`

03筛选前可先用去品牌模式，只移除brands.json所列他牌，原文及其他属性留档，之后由agent筛剩余表达：
`python scripts/clean_materials.py.txt --mode strip-brands --brands brands.json --input 输入.csv --output .tmp-listing/去品牌待筛.json`
brands.json为品牌字符串数组，不能包含自有品牌。此模式不会自动判断剩余表达适用；竞品型号或缺失比较对象仍需agent核对。

ad-a不会将完整问题自动变成关键词。它只清理输入Keyword字段并保留其他字段，按清理结果去重。普通分隔逗号换空格、单引号删除；英文千位分隔转为原数值，其他数字逗号含义不明时进入pending，先问清或由agent核对，不丢弃、不擅改尺寸。否定缩写先展开。

records中的row用于后续计算及四份最终Excel，originals和source_rows暂留JSON供计算，pending由agent集中放入当前块材料表单。块内保存临时JSON后继续依赖顺序；新缺项补齐并发“1”后接着当前块，块完成更新对应Excel。四份最终Excel完整可读、原问关联与排除依据已落表后，清理本项目.tmp-listing/内自行生成的临时JSON，不动原始输入、预处理接手材料、Skill、模板和最终Excel。
