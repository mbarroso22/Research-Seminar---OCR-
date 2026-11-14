"""Synthetic development guards; no fresh filing data or network access."""
import copy
from decimal import Decimal
import unittest

from binding_v3 import bind_answer,normalize_unit,label_matches


def fixture(metric='inventory',label='Inventories (Notes 1 and 3)',title=None):
    income=metric=='net_revenues'
    title=title or ('ACME CONSOLIDATED STATEMENTS OF OPERATIONS' if income else 'ACME CONSOLIDATED BALANCE SHEETS')
    def word(x,y,text,w=75):return [x,y,x+w,y+9,text]
    words=[word(20,20,title,450),word(180,60,'In millions',90),word(400,90,'2022',25),word(530,90,'2021',25),
           word(20,150,label,240),word(400,150,'1,250',35),word(530,150,'1,000',35)]
    page={'doc_id':'financebench:ACME_2022_10K','pdf_page_index':4,'asset_id':'ACME_2022_10K__p004',
          'document_sha256':'f'*64,'width':612,'height':792,'rotation':0,'words':words}
    context={'doc_id':page['doc_id'],'document_sha256':page['document_sha256'],'reporting_currency':'USD',
             'currency_basis':{'document_sha256':page['document_sha256'],'evidence_text':'Independent development fixture: financial statements are denominated in U.S. dollars.'}}
    field={'label':'Total inventories' if metric=='inventory' else label,'year':2022,'value':1250,'unit':'USD in millions','pdf_page_index':4}
    answer={'answer':1250,'unit':'USD millions','source_values':[field],'evidence_pages':[4],'abstain':False,'explanation':'Synthetic development fixture.'}
    spec={'operation':'extract_amount','output_divisor_millions':1,'decimal_places':2,'output_unit':'USD millions',
          'roles':[{'name':'value','year':2022,'label_pattern':'inventor' if metric=='inventory' else 'revenu','unit_kind':'usd_million','allowed_pages':[4]}]}
    return page,context,answer,spec,{'value':metric}


class BindingGuards(unittest.TestCase):
    def bind(self,parts,roles=None):
        p,c,a,s,m=parts
        return bind_answer(a,s,m,p['doc_id'],[4],{(p['doc_id'],4):p},c,roles)

    def test_explicit_unit_grammar_and_recorded_provenance(self):
        p,c,a,s,m=fixture()
        for unit,factor in [('USD (in thousands)',Decimal('.001')),('USD in millions',Decimal(1)),
                            ('Dollars in Millions',Decimal(1)),('$ in millions',Decimal(1)),
                            ('Millions of USD',Decimal(1)),('USD billions',Decimal(1000))]:
            with self.subTest(unit=unit):
                n=normalize_unit(unit,c);self.assertEqual(Decimal(n['factor_to_usd_millions']),factor)
                self.assertEqual(n['original_unit'],unit);self.assertEqual(n['currency_basis'],c['currency_basis'])

    def test_unknown_contradictory_or_mixed_units_decline(self):
        c=fixture()[1]
        for unit in ['USD millions thousands','USD in millions (billions)','EUR millions','CAD millions',
                     'USD/EUR millions','USD in millions (some table)','USD cents','USDX millions','',None]:
            with self.subTest(unit=unit):
                with self.assertRaises(ValueError):normalize_unit(unit,c)

    def test_currency_must_be_known_and_consistent(self):
        parts=fixture()
        for changes in [{'reporting_currency':None},{'reporting_currency':'CAD'},{'currency_basis':{}},
                        {'document_sha256':'0'*64}]:
            altered=copy.deepcopy(parts);altered[1].update(changes)
            self.assertEqual(self.bind(altered)['status'],'held_for_review')

    def test_exact_note_suffix_recognized_and_preserved(self):
        parts=fixture();before=copy.deepcopy(parts[2]);result=self.bind(parts)
        self.assertEqual(result['status'],'table_cell_match')
        self.assertEqual(result['bindings'][0]['cell']['row_label'],'Inventories (Notes 1 and 3)')
        self.assertTrue(result['bindings'][0]['cell']['recognition_trace'])
        self.assertEqual(parts[2],before)

    def test_accounting_qualifier_is_not_removed(self):
        for label in ['Inventories (excluding supplies)','Inventories (Note 1 excluding debt)','Inventories gross']:
            with self.subTest(label=label):
                self.assertEqual(self.bind(fixture(label=label))['status'],'held_for_review')

    def test_total_revenue_requires_task_and_statement_scope(self):
        parts=fixture('net_revenues','Total revenues')
        roles={'value':{'revenue_definition':'consolidated_total_revenues'}}
        self.assertEqual(self.bind(parts,roles)['status'],'table_cell_match')
        self.assertEqual(self.bind(parts,{})['status'],'held_for_review')
        segment=fixture('net_revenues','Total revenues','ACME SEGMENT INFORMATION')
        self.assertEqual(self.bind(segment,roles)['status'],'held_for_review')

    def test_segment_subsection_does_not_inherit_primary_title(self):
        parts=fixture('net_revenues','Total revenues')
        parts[0]['words'].append([20,115,240,124,'Segment information'])
        self.assertEqual(self.bind(parts,{'value':{'revenue_definition':'consolidated_total_revenues'}})['status'],'held_for_review')

    def test_explicit_title_glyph_join_and_company_suffix(self):
        for title in ['Consolidated Balance Shee t','Consolidated Balance Sheets Acme Incorporated and Subsidiary Companies']:
            with self.subTest(title=title):
                self.assertEqual(self.bind(fixture(title=title))['status'],'table_cell_match')

    def test_negative_title_context_is_not_primary_statement(self):
        self.assertEqual(self.bind(fixture(title='Not Consolidated Balance Sheets'))['status'],'held_for_review')

    def test_wrong_page_year_scale_amount_and_sign_held(self):
        for changes in [{'pdf_page_index':5},{'year':2021},{'unit':'USD thousands'},{'value':1000},{'value':-1250},
                        {'pdf_page_index':True},{'value':True},{'value':'1,250'},{'value':float('inf')}]:
            parts=fixture();parts[2]['source_values'][0].update(changes)
            with self.subTest(changes=changes):self.assertEqual(self.bind(parts)['status'],'held_for_review')

    def test_same_value_on_other_row_does_not_resolve_metric(self):
        parts=fixture(label='Other current assets')
        self.assertEqual(self.bind(parts)['status'],'held_for_review')

    def test_duplicate_source_rows_hold(self):
        parts=fixture();extra=[]
        for w in parts[0]['words']:
            if w[1]==150:extra.append([w[0],180,w[2],189,w[4]])
        parts[0]['words']+=extra
        self.assertEqual(self.bind(parts)['status'],'held_for_review')

    def test_contradictory_source_scales_hold(self):
        parts=fixture();parts[0]['words'].append([180,72,270,81,'In thousands'])
        self.assertEqual(self.bind(parts)['status'],'held_for_review')

    def test_foreign_source_currency_header_stays_held(self):
        for header in ['Euros in millions','EUR in millions','In millions of euros','€ in millions','Pesos in millions']:
            parts=fixture();parts[0]['words'][1][4]=header
            with self.subTest(header=header):self.assertEqual(self.bind(parts)['status'],'held_for_review')

    def test_large_wrong_amount_does_not_match_by_decimal_rounding(self):
        parts=fixture();printed=10**40+1234
        parts[0]['words'][5][4]=str(printed)
        parts[2]['source_values'][0]['value']=printed+1
        self.assertEqual(self.bind(parts)['status'],'held_for_review')

    def test_source_identity_and_model_asset_checks(self):
        for changes in [{'asset_id':'wrong'},{'doc_id':'financebench:OTHER_2022_10K'},
                        {'document_sha256':'0'*64}]:
            parts=fixture();parts[2]['source_values'][0].update(changes)
            self.assertEqual(self.bind(parts)['status'],'held_for_review')

    def test_duplicate_operands_hold(self):
        parts=fixture();parts[2]['source_values'].append(copy.deepcopy(parts[2]['source_values'][0]))
        self.assertEqual(self.bind(parts)['status'],'held_for_review')

    def test_unsupplied_top_level_citation_stays_held(self):
        parts=fixture();parts[2]['evidence_pages'].append(29)
        result=self.bind(parts)
        self.assertEqual(result['status'],'held_for_review');self.assertIn('unsupplied_evidence_page',result['reasons'])

    def test_extra_fields_preserved_and_held(self):
        parts=fixture();parts[2]['source_values'].append({'label':'Working capital','value':250,'year':2022,'unit':'USD millions','pdf_page_index':4})
        original=copy.deepcopy(parts[2]);result=self.bind(parts)
        self.assertEqual(result['status'],'held_for_review')
        self.assertEqual(result['supplemental_evidence']['unbound_field_indices'],[1]);self.assertEqual(parts[2],original)

    def test_abstention_never_becomes_candidate(self):
        parts=fixture();parts[2]['abstain']=True
        self.assertEqual(self.bind(parts)['status'],'abstained')


if __name__=='__main__':unittest.main()
