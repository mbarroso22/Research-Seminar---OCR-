"""Post-run numeric-literal screening, not automatic grounding certification.

It checks only whether a declared numeric value occurs in a cited page's native
text. It cannot certify row, column, year, currency or image content. Absent
values need review: charts, extraction gaps and legitimate scale conversion
can also cause absence. It never edits citations or calculator outputs.
"""
import re
from decimal import Decimal,InvalidOperation

def literal_present(text,value):
    if type(value) not in (int,float):return None
    try:target=Decimal(str(value))
    except InvalidOperation:return None
    if not target.is_finite():return None
    clean=re.sub(r'(?<=\d),(?=\d)','',text)
    for token in re.findall(r'(?<![\w.])\(?[-+]?\d+(?:\.\d+)?\)?(?![\w.])',clean):
        try:
            negative=token.startswith('(') and token.endswith(')')
            number=Decimal(token.strip('()'))*(-1 if negative else 1)
            if number==target:return True
        except InvalidOperation:continue
    return False
