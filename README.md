# Listing 工作台：第一版

## 当前主流程

新项目顺序：01导入与基础去重 → 02相似排序分组（embedding+程序，不调用LLM、不删原文）→ 03本品适用性筛选 → 04高重合素材去重 → 05方向分类与属性分级 → 06独立QA选题与回答 → 07短语清洗与本品复核 → 08前缀整理与完整广告词 → 09描述组合与导出。

有新词、新方向或不同条件的素材在04继续保留；待补资料问句进入QA备用池。06读取去重前完整原问及变体。界面和pipeline.py使用同一执行器，每阶段保存Excel和续做提示词。旧项目沿用旧顺序，不按同一编号误用新阶段。下文早期试跑统计及旧导出示例保留作为历史记录。

## 本地可视化工作台

双击 `启动工作台.cmd` 打开独立窗口。关闭窗口会停止本次后台及正在运行的任务。操作说明见 [本地工作台使用说明.md](本地工作台使用说明.md)。

界面支持多CSV导入、本品完整资料、硅基流动LLM/embedding模型选择、分阶段运行和Excel下载、合并前第二次本品自查、人工修改后重新组合。广告词保持完整，描述单独合并重合前缀，9000字符仅为上限。阶段00—09各产Excel。

本品资料区可输入ASIN或完整Amazon商品链接读取标题、五点、规格及A+文字，回填可撤销。界面读取使用Chrome/Edge本地DevTools协议，不需要Node.js或Playwright；原始页面与快照保存在 `工作区/captures/`。普通描述为空可继续，验证码或ASIN不符不会回填成成功资料。

已用两份真实CSV验证界面导入（1064条来源），用4条原始记录的小样完成全部9阶段并生成00—09共10份Excel；实测模型列表、人工自查修改后的重新组合、独立窗口关闭后的后台退出及任务子进程停止。大批量LLM阶段耗时取决于所选模型，页面显示阶段进度；结果仍需内容核对。

配套skill位于 `skills/listing-material-workflow/SKILL.md`，详细阶段列说明在其 `references/stages.md`。可独立用于不用本机程序的AI工作流。

目前可抓取详情、导入去重、语义判断、分级、从原问独立选QA，并将商品适用性筛选、素材清洗、归并、描述组合与导出串联。不需要登录八面马。

## 从现有结果串跑到素材导出

```powershell
C:\Python313\python.exe pipeline.py --input output/cleaning-semantic-first --product products/B0BW8JZ279.json --grades output/grading-keywords-confirmed/graded_groups.json output/grading-questions-confirmed/graded_groups.json --judgments output/judgment-final/judgments.json --qa output/qa-selected-edit/qa_selection.json --decisions products/B0BW8JZ279_material_decisions.json --out outputs/本次素材 --xlsx
```

也可用 `--csv 文件1.csv 文件2.csv ...` 或CSV目录从原始导出启动，数量不限于两份。不传已有分级、关系、QA时，程序依次调用相应模块；QA始终使用原问，素材合并另行进行。旧分级按类型、站点与原文复用，避免新文件加入后组ID变化引起错配。`--csv` 应选择新的输出目录，模型缓存继续复用。

商品适用性分为可用、明确不符、资料不足、仅已确认子体可用。只有可用项进入素材归并；其他原文、状态和原因全部保留。适用性属于模型建议，人工修正可通过 `--decisions` 按类型与原文应用，原建议另存，不重新请求模型。QA可保留缺资料的重要问题，不能反过来把它们当成已确认的广告卖点。

导出关键词、完整问句、整理后的问句三个CSV和按类型/等级分Sheet的素材Excel，附不适用及待补资料明细。清洗保留否定、fit over等会改变含义的关系；数量/程度仍需改写的表达明确标记，暂不放入组合描述。已选QA实际覆盖的问句可保留完整表达，其他问句采用清洗短语。

`商品描述素材草稿.txt` 是供核对的组合素材，不自动上传。9000字符只是默认上限，可用 `--max-characters` 调整；不填充到上限，不截断单条。通过新词及相邻词组合减少重复，不把“单词都出现过”当成语义已被覆盖，也不据此删除原始素材。新流程组合选择明细保存在 `stage9.json`，早期试跑保存在 `materials.json`。

当前两份文件的实跑输出在 `outputs/01a1d4ae-2cd3-7ac0-9232-a9932a740270/B0BW8JZ279_素材试跑`：1064条来源、1059组原文全部保留；320组进入可用素材，归并后149组关键词和104组问句。142组不适用、597组待补资料另列；并非删除，也不表示商品确认没有待补功能。描述草稿8267字符，按自然信息增量组合。Excel共18张表，统一固定行高30、不冻结、首行表头。人工修正可同时包含 `level`，用于修正已核对的分级，不改原始模型缓存。

此轮串跑覆盖已有CSV到素材导出；自动发现并按价格/功能/外观选择竞品、评论抓取分析、逐个子体采集仍未接入。QA保持独立草稿，清洁方法、套镜兼容性、变色速度仍待补资料。以上处理结果需要最终内容核对，不自动上传卖家后台。

## 抓 Amazon 详情页

需要本机 Chrome 和 Node.js。安装依赖：`npm.cmd install`。

```powershell
npm.cmd run capture -- B0BW8JZ279
npm.cmd run capture -- https://www.amazon.com/dp/B0BW8JZ279
```

ASIN 默认美国站；其他站可传完整商品链接，或使用 `--domain www.amazon.de`。
`--headed` 显示浏览器；默认使用独立无登录浏览器，不读取个人浏览器账户。

每次保存到 `output/products/ASIN-时间/`：`page.html` 是当时页面，
`product.json` 包含标题、可见价格原文、五点、参数、A+ DOM 文字和图片引用、页面中的变体入口。
折叠区已存在 DOM 的文字也会提取；图片没有 OCR，子体未逐个抓取，未采集评论或社区问答。
页面宣传统一标为 `listing_claim`，不是已核实商品事实。

`missing_sections` 列出没抓到的五点/参数，不把空值解释为商品没有该属性。
普通商品描述和 A+ 未读取到时记在 `optional_absent_sections`，不视为采集失败。
`partial` 表示关键区域缺失；验证码、ASIN 不匹配、网络错误会报错，不能作为成功详情使用。
价格未统一币种、优惠券或配送地区，暂不用于自动筛选高价竞品。

## 批量抓取并关联清洗结果

从已导入的 `sources.json` 提取 ASIN 和站点，不需要再逐个粘贴链接。
同站点同 ASIN 只抓一次；`--own` 指定自家商品（多个用逗号分隔），其余标为竞品。

```powershell
npm.cmd run capture:batch -- --sources output/cleaning-first-run/sources.json --own B0BW8JZ279 --out output/batches/first-comparison
```

批次目录的 `index.json` 保存每个商品的详情文件、来源 ID、站点和自家/竞品角色。
某一页失败仍继续下一页；每抓完一页就更新索引。续跑时加 `--resume`，并使用同一 `--out`：

```powershell
npm.cmd run capture:batch -- --sources output/cleaning-first-run/sources.json --own B0BW8JZ279 --out output/batches/first-comparison --resume
```

续跑跳过可读取的成功快照，重新抓取失败、部分缺失或文件丢失的商品。
详情是采集时的快照；想刷新成功商品，运行一个新批次。

再次清洗时附上 `--products output/batches/first-comparison/index.json`，
输出 `sources.json` 中每条原记录会关联其 ASIN 和站点对应的详情。
失败或尚未抓取的商品明确标记状态。关联不会把竞品卖点改为自家卖点，也不会自动过滤词或判定事实。

## 去重两份或多份八面马 CSV

Python 3，无第三方依赖：

```powershell
C:\Python313\python.exe cleaner.py "八面马拓展词\Alexa买家意图拓词-B0BW8JZ279-v1.csv" "八面马拓展词\Alexa买家意图拓词-B07W52VH1X-v1.csv" --out output\my-review
```

也可以传入 CSV 文件夹。输出目录必须是新目录，避免覆盖人工复核结果。

- `sources.json`：每条完整原记录、来源文件和 CSV 记录位置（包含表头；多行字段不是物理行号）。
- `groups.json`：完全重复和规范化重复的关联，保留全部来源和 ASIN。
- `关键词去重.csv`、`问句去重.csv`：分别查看结果；未知类型单列。
- `相近项待复核.csv`：字面相近的候选，默认最多 500 对。不是语义模型结果，不自动合并。
- `summary.json`：导入数、独立文本组数、ASIN 数、候选总数和运行时间。

归并只统一大小写、空格、全半角、部分排版符号和句尾问号等；保留数字小数点、单位、否定和属性关系。
不同站点、关键词与问句分开归并。同一问句跨 ASIN 可共用文本组，原答案和商品依据始终保留在各自源记录。
重复传同一路径不会重复导入；重新运行产生独立结果，没有跨运行累加数据库。

问句的 `phrase_candidate` 去掉 `for` 和部分提问外壳，但不作为去重依据，不自动判定适用性。
`fit over`、`without` 等关系保留；含糊的 how long/how dark 等留待改写。
语义关系、人工复核与分级草稿见后文。商品适用性由后续 `applicability.py` 或 `pipeline.py` 处理，基础CSV导入步骤本身不判断。

## 硅基流动语义候选

```powershell
C:\Python313\python.exe cleaner.py "八面马拓展词\Alexa买家意图拓词-B0BW8JZ279-v1.csv" "八面马拓展词\Alexa买家意图拓词-B07W52VH1X-v1.csv" --products output/batches/first-comparison/index.json --similarity siliconflow --out output/my-semantic-review
```

密钥依次从进程环境变量、Windows 用户环境变量读取，支持 `SILICONFLOW_API_KEY` 和 `siliconflow`。
不需要把密钥复制到代码、命令行或配置文件。仅向硅基流动官方 embedding 接口发送待比较的词和问句，不发送整份商品资料。

默认模型 `BAAI/bge-m3`，可用 `--embedding-model` 改为账户可用的其他文本 embedding 模型。
默认每批 32 条，`--embedding-batch-size` 可调。向量按模型和原文存入 `output/embedding-cache.sqlite3`，每批成功后提交，失败重跑会复用完成部分。
模型不同时分开缓存。缓存不保存密钥，完全命中时不读取密钥、不调用 API。
`--embedding-cache` 可指定其他缓存路径。API 429 和部分服务/网络错误最多尝试 3 次；调用用量记录在结果 summary 中。

语义模式输出 `语义相近项待复核.csv` 和 `semantic_metadata.json`：

- 每条记录在同站点、同类型内找最相近的 5 条，默认余弦相似度至少 0.75。这是初始候选参数，不是已校准的合并标准。
- `--neighbors`、`--semantic-threshold` 可调整；各条候选取并集，不用全局前 500 对截断，避免只剩热门主题。
- 展示原问、语义相似度、词项重合度、双方独有词和部分条件差异提示；条件提示只是规则辅助，不保证覆盖所有差异。
- 词项重合度是去掉部分结构词后的集合交并比，仍包含商品核心词，不等于信息覆盖率。
- 关系状态始终为 `unjudged / needs_review`。同义重复、部分重合、仅同主题需要下一步 LLM/人工判断；没有按分数自动合并或删除。
- 代表问句、原始关键词、精简短语分别保存；精简短语不作为 embedding 输入。

如已安装 NumPy，会用于加速向量比较；否则使用标准 Python 计算，结果规则相同。没有新安装第三方依赖。
省略 `--similarity siliconflow` 仍使用原来的字面候选，不产生 embedding 请求。

## LLM 判断候选关系

```powershell
C:\Python313\python.exe judge.py --input output/cleaning-semantic-first --out output/my-judgment-review
```

默认使用硅基流动 `deepseek-ai/DeepSeek-V4.1-Flash`，可用 `--model` 更换。
沿用 embedding 的用户环境变量读取，不复制密钥。只发送每对原始词/问句及文本类型，不发送商品事实或 embedding 分数。
用 `--limit 24` 小样试跑；不填处理全部候选。默认每批12对、3个并行请求，可用 `--batch-size` 和 `--workers` 调整。

输出 `语义关系复核.csv`、`judgments.json` 和 `summary.json`，包含：

- 同义重复、部分重合、仅同主题、不同意图、不确定，以及请求失败时的“未判断”。
- 共同意图、左右独有的信息及对应的连续原文片段、两个方向的信息覆盖关系、是否有可能共用具体短答案。
- 主题和简短判断理由。主题标签目前服务太阳镜样本；换类目需要调整。
- 全部为模型建议，不自动合并、删除或改写原文，也不依据配对关系传递合并其他问句。

同义判断要求没有独有信息并且双向覆盖；能共用答案并不等于同义。模型只判断语言关系，不验证商品参数，也不把生成问句称为真实买家历史。
覆盖方向按模型列出的独有信息计算：部分重合时只有左侧有新增要求，则左覆盖右；双方都有新增要求则互不覆盖。同义则双向覆盖，其余不推定覆盖。
原模型的覆盖说法保存在 `reported_coverage`，与计算结果不一致时在复核页提示。计算依赖差异列表，不代表已经核实模型是否完整、正确地提取信息。
模型提供的独有信息、原文片段与原始返回一起保留供核对；不因字段小问题或引文措辞不同自动打回重跑。
错误请求单独保留“未判断”，不伪装成模型的“不确定”。
结果按模型、实际提示词、文本类型和原始文本对存入 `output/judgment-cache.sqlite3`；重跑复用成功项，失败项重新请求。
输入顺序/组ID改变不会错用旧ID。更换模型或提示词后重新判断，不会复用不对应的旧结果。
`--cache` 可另选缓存；API调用可能产生费用，用量记录在 summary。

## 本地人工复核页

```powershell
C:\Python313\python.exe review.py --input output/my-judgment-review
```

在结果目录生成独立 `review.html`，浏览器打开即可搜索、筛选、并排查看原文和差异依据。
如果原清洗目录仍可读取，也展示对应 ASIN、来源文件、记录位置和导出文件中的依据原文。
可以改选关系、确认、撤销，并导出/导入确认记录 JSON。浏览器本地存储仅供方便，导出文件用于另存进度。
确认针对当前文本对，不将配对关系传递成整个簇，也不删除源记录。

需要将人工确认应用到程序输出时，保留原结果，生成一份新结果：

```powershell
C:\Python313\python.exe review.py --input output/my-judgment-review --decisions "关系确认记录.json" --out output/my-confirmed-review
```

程序按组ID和原文匹配记录。人工结果单列 `reviewed_relation`，原模型建议和原问不被改写。
分级与QA均为草稿；素材组合由 `pipeline.py` 单独执行，不自动发布。

QA 单独产出一张表，与关键词等级分级分开。QA 表按提问方向、代表问句、覆盖的原问、回答与译文、商品资料依据、待确认事项整理；选题不以关键词属性等级为门槛。清洁、保养等没有额外商品限定的问题仍保留为候选，不因零属性删除。

QA选题在广告/商品描述素材的语义合并之前进行。`qa.py` 只读取原问及其方向、来源和自家商品资料，不读取语义合并建议、关键词等级或来源Evidence。自家与竞品原问都可提供选题；回答只依据自家资料，缺资料的问题保留备用。每个方向先提取1—3条具体QA草稿，关联当前短答案能覆盖的原问。广告/商品描述的合并结果保持独立。

```powershell
C:\Python313\python.exe qa.py --input output/cleaning-semantic-first --assessments output/grading-questions-manual-review --product products/B0BW8JZ279.json --out output/qa-from-originals
```

输出 `qa_selection.json` 和 `原问选题明细.csv`；每个方向的输入与模型原始返回保存在同目录，已完成方向可续用。原问明细不因未选用而删除，也不视为真实消费者热度。`tools/xlsx/export-qa.mjs` 将QA单独导出为一个工作表，含QA与A+双语草稿、依据、待确认事项及可填写的复核意见。

使用 `--selection products/B0BW8JZ279_qa.json` 可直接采用已编辑选题，不发起模型请求。回答待补资料的选题与已写回答区分，不能把只有选题的原问标成已被答案覆盖。单个方向请求失败不阻止其他方向输出，失败方向的原问仍保留。

## 代表问句与同义词归并建议

```powershell
C:\Python313\python.exe intents.py --groups output/cleaning-semantic-first/groups.json --judgments output/my-judgment-review/judgments.json --own B0BW8JZ279 --out output/my-intent-proposals
```

输出问句/关键词建议表和 `intent_proposals.json`。每组先选一条代表原文，只加入与代表原文有直接同义建议的成员，不沿A-B-C-D链条一路归并。
存在已知非同义关系的成员不放进同组；带条件差异提示的模型同义建议先单列，人工确认后可以采用。
人工确认优先于原模型建议。每条原文、变体、来源ID和ASIN全部保留，未归并的记录单列。
代表文本排序优先有更多直接同义候选的文本，其次偏向自家商品来源。参考主题来自关系建议，尚不等于完成了7—8类的最终选题。
来源记录数与ASIN数分别统计，不代表消费者提问热度。输出仍为草稿建议，不会自动删除原问、合并商品事实或发布文案。
如果关系判断尚未全部完成，summary 会标明可用关系数和总候选数，不把阶段性归并数量当成最终结果。

## 核心词与属性重新分级

```powershell
C:\Python313\python.exe grading.py --input output/cleaning-semantic-first --out output/my-keyword-grading
```

默认只处理关键词。模型从原文抽取核心词、完整语义属性及原文依据，程序按不同属性概念计数，不接收模型直接给的等级，也不把来源旧等级发给模型。
`14cm arm length` 是一个属性，`fit over prescription glasses` 是一个属性。UV400与UV protection重复概念合并，核心词内部属性不重复计数，help with等结构词不计数。
程序对明确形状词作补充识别；其他未被解释的关键词修饰词放入待复核，避免漏属性后给出过低等级。

结果包含 `graded_groups.json` 和 `分级草稿.csv`，展示来源旧等级、新等级、属性明细、方向、ASIN和来源ID。
疑义记录的新等级留空，已识别属性数另存。原文不改，分级不等于商品适用性判断。
属性分析不再因字段缺漏、类型不符或依据非逐字引用而自动打回重跑。模型原始返回保存在 `raw_response`，导出所需的缺失字段使用空值；最终人工核对。只在请求失败、返回无法读取或无法对应原问时记录失败，本层不自动重试。旧缓存继续复用。

默认使用硅基流动同一文本分析模型，结果缓存到 `output/assessment-cache.sqlite3`，修正计数规则后可复用原始属性提取，不必重复请求。

`--kind ai_generated_question` 分析问句，`--kind all` 同时分析两类。按小雨确认的口径，默认 `--question-policy attributes-only`，只数商品限定属性，提问方向单独分类。例如 `How do I clean these sunglasses?` 是0级，清洁方向不加级，也不影响选入QA。
默认 `--activity-policy per-value`，例如 `sunglasses for fishing and golf` 中钓鱼与高尔夫分别算一个限定，共2级。`--from-assessments 已有graded_groups.json` 可直接复用属性重算等级，不请求模型。
问句会抽取被问到的属性，例如“是否偏光”包含偏光关注属性，但绝不因此认定商品具备偏光。

## 分级 Excel 导出

`tools/xlsx/export-grades.mjs` 使用 Codex 随附的表格运行库导出。准备运行库的 node_modules 关联后，使用该运行库的 Node.js：

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" tools/xlsx/export-grades.mjs --input output/my-keyword-grading --sources output/cleaning-semantic-first/sources.json --out outputs/关键词分级草稿.xlsx
```

每个等级一张 Sheet，待复核记录单列，来源记录单独保留。数字等级和CSV记录位置保持数值类型；原文、ASIN和来源ID保持文本。
关键词与QA统一从第1行表头开始，不放表前说明，不冻结，表头行高16.5、正文默认14，需要两行时28，列宽保持紧凑。不自动覆盖已有文件；明确传 `--overwrite` 可更新指定导出文件。`--render-dir` 可保存各工作表的预览用于检查。

## 自家商品资料

`products/B0BW8JZ279.json` 保存小雨提供的标题、规格、包装和用途，与抓取的页面宣传分开。
脸型、套镜、重量、车内变色等已知疑点单列，不擅自补全。当前该文件用于后续适用性筛选的准备，分级阶段不据此删词。

## 检查

```powershell
C:\Python313\python.exe -m unittest -v test_cleaner test_semantic test_judge test_review test_intents test_grading
npm.cmd run test:capture
npm.cmd run test:review
node --test xlsx-plan.test.mjs
```

商品资料补充：小雨暂时保留“小中脸”现有写法。142mm 框宽和一条“不适合窄脸”的差评形成待核对事项，不能据此自动确认小脸适配；此处仅记录本次决策，未自动过滤词或修改页面。
