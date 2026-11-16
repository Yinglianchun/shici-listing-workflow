import copy
import json
import tempfile
import unittest
from pathlib import Path
from review import apply_decisions,build_review


class ReviewTests(unittest.TestCase):
    def test_manual_relation_does_not_rewrite_source_or_model_suggestion(self):
        row={'left':'A','right':'B','left_text':'small faces','right_text':'large faces','relation':'equivalent','status':'needs_review'}
        before=copy.deepcopy(row)
        result=apply_decisions([row],{'decisions':[{'left':'A','right':'B','left_text':'small faces','right_text':'large faces','relation':'same_topic'}]})
        self.assertEqual(row,before)
        self.assertEqual(result[0]['relation'],'equivalent')
        self.assertEqual(result[0]['reviewed_relation'],'same_topic')
        self.assertEqual(result[0]['status'],'confirmed')
        with self.assertRaises(ValueError):
            apply_decisions([row],{'decisions':[{'left':'A','right':'B','left_text':'old text','right_text':'large faces','relation':'same_topic'}]})

    def test_report_escapes_script_closing_tags_in_source(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'judgments.json').write_text(json.dumps([{'left_text':'</script><script>bad()</script>'}]),encoding='utf-8')
            (folder/'summary.json').write_text('{}',encoding='utf-8')
            result=build_review(folder).read_text(encoding='utf-8')
            self.assertNotIn('</script><script>bad()',result)
            self.assertIn('\\u003c/script>',result)


if __name__=='__main__':
    unittest.main()
