"""Build the stage templates once, then install the same files into the workflow skill."""
import shutil
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stage_templates import templates
from excel_export import export_excel

root=Path(__file__).resolve().parents[1]
output=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'outputs/01a1d4ae-2cd3-7ac0-9232-a9932a740270/ASIN_日期_流程模板'
work=root/'output/template-build'
assets=root/'skills/listing-material-workflow/assets'
installed=Path.home()/'.codex/skills/listing-material-workflow/assets'
local=root/'templates/ASIN_日期_流程模板'
for folder in [output,work,assets,installed,local]:folder.mkdir(parents=True,exist_ok=True)
for name,plans in templates().items():
    if len(sys.argv)>2 and name not in sys.argv[2:]:continue
    export_excel(plans,work/name)
    for folder in [assets,installed]:shutil.copyfile(work/name,folder/name)
    public_name='ASIN_日期_'+('05_关键词分级.xlsx' if name=='关键词分级空模板.xlsx' else name)
    for folder in [output,local]:shutil.copyfile(work/name,folder/public_name)
    if name in ('关键词分级空模板.xlsx','素材总表空模板.xlsx','QA与A+问答空模板.xlsx'):shutil.copyfile(work/name,root/'templates'/name)
print(str(output))
