import json,unittest
from integrated_processing import strict_contract
class ContractTests(unittest.TestCase):
 def test_abstention(self):
  self.assertTrue(strict_contract(json.dumps({'answer':None,'unit':'','source_values':[],'evidence_pages':[],'abstain':True,'explanation':'Missing evidence.'})))
 def test_bad_number(self):
  self.assertFalse(strict_contract('{"answer":NaN}'))
 def test_extra_key(self):
  self.assertFalse(strict_contract('{"answer":null,"extra":1}'))
if __name__=='__main__':unittest.main()
