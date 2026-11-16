import unittest
from pathlib import Path
from product_capture import product_url,page_issue

class ProductCaptureTests(unittest.TestCase):
    def test_link_and_asin_use_same_canonical_entry(self):
        expected=('B0BW8JZ279','https://www.amazon.com/dp/B0BW8JZ279')
        for text in ['B0BW8JZ279','https://amazon.com/dp/B0BW8JZ279','https://www.amazon.com/dp/B0BW8JZ279?th=1']:
            self.assertEqual(product_url(text),expected)

    def test_actual_failed_page_is_access_challenge_not_empty_product(self):
        saved=Path('工作区/captures/11a49940dd4f4917bd791988d7622ec1/page.html')
        self.assertEqual(page_issue('Click the button below to continue shopping'),'blocked')
        if saved.exists():self.assertEqual(page_issue('',saved.read_text(encoding='utf-8')),'blocked')
        self.assertEqual(page_issue('type the characters you see'),'blocked')
        self.assertEqual(page_issue('ERR_CONNECTION_RESET'),'network_error')
        self.assertIsNone(page_issue('Premium sunglasses product details'))

if __name__=='__main__':unittest.main()
