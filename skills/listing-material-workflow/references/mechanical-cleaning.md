# 初步机械清洗脚本

01之前：先选本轮各版本CSV，运行core-terms模式抽取CoreTerm/Category候选，再由agent预填集中确认表单，问核心泛词是否需要补充。此模式不要求Keyword字段、不改原文、不推断全部Keyword都是核心。

`python scripts/clean_materials.py.txt --mode core-terms --input 各版本素材.json --output "步骤备份/00_本品分析/核心候选.json"`

第01步：用户使用的AI环境支持代码运行时，默认由当前agent在该环境运行scripts/clean_materials.py.txt；不要求用户电脑安装Python，不需要API Key或第三方包。文件是Python源码，保留.txt后缀便于传递，直接交给Python解释器即可。无代码环境时用文件工具完成相同规则，不声称脚本已执行。

脚本只合并**格式规范化后完全重复**：统一大小写、空格、全半角及已约定末尾标点，原文保留。**01 dedup、ad-a及sales-terms模式均不提前合并women/womens/所有格、for women、单复数或调序变体**；这些只作02比较候选或05核心分级匹配。只有在06确认没有任何核心之外的其他限定、且确属同一已确认完整核心，才允许合并裸核心的明确写法变体。关键词、问句都不按拆词排序判重；red frame blue lenses与blue frame red lenses必须分开。顺序不同、属性/部件归属不同、否定、数值或条件不同都不机械删除。

同顺序、整词连续完整包含仅写containment_candidates，记录short_id/long_id、双方文本及pending_applicability状态；id对应records的original_order，即输入行序号。双方仍保留在records，不因包含链间接删除，也不把sun当作sunglasses中的完整词。候选只在相同sheet、站点和素材类型中比较。比较包含关系时必须按整词和实际限定判断。women 与 men 是不同人群，字母重合不构成重复或包含。women sunglasses 与 men sunglasses、for women 与 for men 均分别保留；women、womens、women’s 的等价拼写规则仅在女款写法之间适用。03确认本品适用性后，由04判断完整覆盖并记候选，06各条独立提炼与分级。完全包含只是一条比较线索，06禁止依据包含、同义、词序变化或单复数合并带限定的表达，哪怕同Sheet同等级；只有01格式规范化后完整一致的表达可以直接合并，另有无额外限定的裸核心词写法例外。长短问仍原样留供QA，不用回答相同替代判重。新增限定或独立用途时分别保留。

脚本还可字面排序、移除已确认品牌及清理广告A列标点：普通关键词及已提炼长问只移除无意义标点，**词内连字符`-`必须保留**，小数点及数值单位不能破坏；**未经提炼的原问不足80字符时，只去问号、保留其余原文标点与句式**。达到80字符的原问须由06人工/agent提炼后再清理，脚本`ad-a`对此类未处理原问返回pending，不能当作已完成。问句的描述用清洗表达独立由06填写F列，脚本不自动提炼关键表达，不判断本品适用性、属性级别、同义覆盖或选QA写描述，也不调用其他LLM。字面排序及包含候选都不是语义结论。

输入为CSV或JSON行对象数组，必须有Keyword；Type或kind区分keyword和question，无法确认的标unknown，不按词序合并。跨Sheet输入加sheet字段，避免把不同表页互相删除；来源或其他列放同一行对象即可保留。Excel用环境表格工具读取为行对象，不把原文或来源字段改成清洗值。

## 脚本拿不到时

能运行代码时，由当前agent在项目临时目录用Python标准库写一个小脚本，只实现本轮实际需要的处理。用 `csv.DictReader`（兼容UTF-8 BOM）或 `json` 读取各来源，按上文的字段及范围分组。每组输出代表行及全部原文和来源行号（`records` 中的 `row`、`originals`、`source_rows`），将包含或高度重合的词句另记为比较候选。保留输入文件，输出临时JSON。涉及核心词、出单词、已确认品牌或广告标点时，只按本文对应规则增加所需处理。

运行真实素材前，先用几行样例确认：同顺序的格式上完全重复保留一个代表且原文都在；women sunglasses 与 sunglasses women 在01只作为高重合候选，06仅在确认无额外限定的裸核心时允许合并；retro women sunglasses 与 women sunglasses retro 必须保留两条；红框蓝片与蓝框红片仍各有一条。检查结果再处理原始素材。03的适用性由当前agent判断，04只整理对比候选、不执行语义去重；06才按同文或裸核心例外决定是否合并。环境不能运行代码时，使用可用的文件或表格工具处理，按实际能力说明完成了哪些步骤。

## 年度用户搜索词报告

分级前导入，不等最后才拼表。默认「广告搜索词」导出按本品口径关联当前项目，直接读取文件名或报告里已有的时间范围。无ASIN列不需要再确认报表范围。只有已知跨商品或资料明确冲突时才核对，未提供子体明细时按本品汇总使用；01先用sales-terms模式机械整理，再并入拓词池，接02排序、03适用性、04保守去重、05核心汇总与06分级。若项目已经完成分级，只对新增报告做同样整理、核对和分级后更新总表，不仅按词长塞进已有等级，也不重跑无关QA或描述。

用户这类导出只保留“用户搜索词”“订单数”两列，不要求额外销售额列。按用户确认的此类导出格式，保留表头，默认直接删除表头后的第一条数据行（总订单汇总行），不依赖其文字识别。若输入已经手动删过该行，调用时加--keep-first-row，避免误删第一条真实搜索词。脚本也移除第一列值为“总订单数/合计/总计/Grand Total”等的汇总行、空搜索词、0订单行，以及整格为B开头10位字母数字且含数字的ASIN行（忽略大小写）。不按B开头就删普通单词，不删除仅包含ASIN的完整搜索短语。只保留订单数明确大于0的行，订单数缺失或不明确时不猜成0，留给agent在本轮集中核对。

`python scripts/clean_materials.py.txt --mode sales-terms --input 年度搜索词.csv --output "步骤备份/01_基础去重/年度出单词.json"`

若原列名不同，先读表头，再用`--term-column "实际搜索词列名" --orders-column "实际订单列名"`映射。Excel先用环境表格工具转CSV或行对象JSON，不要求用户电脑装Python。terms只包含两列的整理结果；records可直接进入后续流程，原词变体保留在originals中，Type标为keyword。

同一份完整年度导出中，只按大小写、空格、全半角及无实质尾部标点合并格式重复并累计订单，按订单数降序；women/womens/所有格等变体即使属于同一核心概念，也不在报告整理时直接合并订单，原词订单始终分开留档；不做语义去重、不把近义场景强行合并。不同产品、不同报告或重叠时间窗分开执行，不把重复导出直接叠加订单。与AI拓词合并时保留订单依据，但不给AI拓词编造订单。随后移除竞品品牌时，订单始终属于原始搜索词，不能把“miu miu sunglasses”订单冒充为去品牌后的“sunglasses”自然出单。

若提供的是有销售额而没有订单数的另一类报告，按实际字段筛销售额大于0并保留指标，不伪造订单数，也不调用sales-terms强猜列。此脚本不自行判断哪个出单词适用、值得投或应否定。

当前只做01时使用：
`python scripts/clean_materials.py.txt --mode dedup --input 输入.csv --output "步骤备份/01_基础去重/基础清洗.json"`

第02步承接01输出：读取基础清洗.json中的records，row为保留文本，originals及source_rows为来源映射；结合containment_candidates和字面顺序组织比较候选。可按文本重合度把只疑似换序或单复数变化的表达排近，例如 women sunglasses / sunglasses women。排序和分组只供当前agent在03之后的04比较，不更改去重结果。无需重复dedup；脚本不提供embedding，不据字面排序或包含关系删除语义近似项。完成02保存临时JSON，继续第二块的03，不额外交付阶段Excel。

当前只做06且agent已提炼关键表达后使用：
`python scripts/clean_materials.py.txt --mode ad-a --input 广告A列及原文.json --output "步骤备份/06_提炼复核分级/广告A列清理.json"`

03筛选前可先用去品牌模式，只移除brands.json所列他牌，原文及其他属性留档，之后由agent筛剩余表达：
`python scripts/clean_materials.py.txt --mode strip-brands --brands brands.json --input 输入.csv --output "步骤备份/03_本品适用性/去品牌待筛.json"`
brands.json为品牌字符串数组，不能包含自有品牌。此模式不会自动判断剩余表达适用；竞品型号或缺失比较对象仍需agent核对。

ad-a不会将完整问题自动变成关键词。它只清理输入Keyword字段并保留其他字段，按清理结果去重。普通分隔逗号换空格、单引号删除；英文千位分隔转为原数值，其他数字逗号含义不明时进入pending，先问清或由agent核对，不丢弃、不擅改尺寸。否定缩写先展开。

records中的row用于后续计算及四份最终Excel，originals和source_rows暂留JSON供计算，pending由agent集中放入当前块材料表单。块内保存临时JSON后继续依赖顺序；新缺项补齐并发“1”后接着当前块，块完成更新对应Excel。四份最终Excel完整可读、原问关联与排除依据已落表后，保留“步骤备份/”供复核。以后清理直接删除该目录即可。
