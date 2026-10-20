"""Bounded character recognizer for the pinned converter's GBNF subset.

Pure standard library: no vocabulary, weights, backend or inference. Unsupported
syntax fails closed. Tests cross-check this recognizer against pinned C++ code.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import json
import re


@dataclass(frozen=True)
class Terminal:
    value: str
    character_class: bool = False


class Grammar:
    def __init__(self, text: str):
        if len(text)>100_000:raise ValueError('Grammar too large')
        self.rules={};self.serial=0;self.classes={}
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith('#'):continue
            name,separator,rhs=line.partition('::=')
            name=name.strip()
            if not separator or not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*',name) or name in self.rules:
                raise ValueError('Invalid or duplicate GBNF rule')
            self.tokens=self._tokens(rhs);self.position=0
            self.rules[name]=self._alternatives()
            if self.position!=len(self.tokens):raise ValueError('Unsupported GBNF suffix')
        if 'root' not in self.rules:raise ValueError('GBNF root missing')
        if len(self.rules)>4096:raise ValueError('Too many grammar rules')
        for alternatives in self.rules.values():
            for production in alternatives:
                for symbol in production:
                    if isinstance(symbol,str) and symbol not in self.rules:raise ValueError('Undefined grammar rule: '+symbol)
        self.nullable=set()
        while True:
            found={name for name,alts in self.rules.items() if any(all(isinstance(s,str) and s in self.nullable for s in p) for p in alts)}
            if found<=self.nullable:break
            self.nullable|=found

    def _tokens(self, rhs):
        result=[];i=0
        while i<len(rhs):
            c=rhs[i]
            if c.isspace():i+=1;continue
            if c=='"':
                start=i;i+=1
                while i<len(rhs):
                    if rhs[i]=='\\':i+=2
                    elif rhs[i]=='"':i+=1;break
                    else:i+=1
                else:raise ValueError('Unclosed grammar string')
                try:value=json.loads(rhs[start:i])
                except ValueError as exc:raise ValueError('Unsupported grammar string escape') from exc
                result.append(('literal',value));continue
            if c=='[':
                start=i;i+=1
                while i<len(rhs):
                    if rhs[i]=='\\':i+=2
                    elif rhs[i]==']':i+=1;break
                    else:i+=1
                else:raise ValueError('Unclosed character class')
                value=rhs[start:i]
                # GBNF classes are codepoint ranges/literals, not Python categories.
                if re.search(r'\\[dDsSwWpP]',value):raise ValueError('Unsupported class category')
                self.classes[value]=re.compile(value+r'\Z')
                result.append(('class',value));continue
            m=re.match(r'[A-Za-z][A-Za-z0-9-]*|[0-9]+',rhs[i:])
            if m:result.append(('name' if m[0][0].isalpha() else 'number',m[0]));i+=len(m[0]);continue
            if c in '|()*+?{},':result.append((c,c));i+=1;continue
            raise ValueError('Unsupported GBNF token: '+c)
        return result

    def _new(self, alternatives):
        name='internal-'+str(self.serial);self.serial+=1
        while name in self.rules:name='internal-'+str(self.serial);self.serial+=1
        self.rules[name]=tuple(tuple(p) for p in alternatives)
        return name

    def _take(self, kind):
        if self.position>=len(self.tokens) or self.tokens[self.position][0]!=kind:raise ValueError('Unexpected grammar syntax')
        value=self.tokens[self.position][1];self.position+=1;return value

    def _peek(self):return self.tokens[self.position][0] if self.position<len(self.tokens) else None

    def _alternatives(self):
        alternatives=[]
        while True:
            sequence=[]
            while self._peek() not in (None,'|',')'):
                kind=self._peek()
                if kind=='name':atom=self._take('name')
                elif kind=='class':atom=Terminal(self._take('class'),True)
                elif kind=='literal':atom=self._new([[Terminal(c) for c in self._take('literal')]])
                elif kind=='(':
                    self._take('(');atom=self._new(self._alternatives());self._take(')')
                else:raise ValueError('Unexpected grammar atom')
                repeat=self._peek()
                if repeat in ('*','+','?'):
                    self._take(repeat)
                    if repeat=='?':atom=self._new([[],[atom]])
                    else:
                        tail=self._new([]);self.rules[tail]=((),(atom,tail))
                        atom=tail if repeat=='*' else self._new([[atom,tail]])
                elif repeat=='{':
                    self._take('{');minimum=int(self._take('number'));maximum=minimum
                    if self._peek()==',':
                        self._take(',');maximum=int(self._take('number')) if self._peek()=='number' else None
                    self._take('}')
                    if minimum>256 or maximum is not None and (maximum<minimum or maximum>256):raise ValueError('Unsupported repetition bound')
                    if maximum is None:
                        tail=self._new([]);self.rules[tail]=((),(atom,tail))
                    else:
                        tail=self._new([[]])
                        for _ in range(maximum-minimum):tail=self._new([[],[atom,tail]])
                    atom=self._new([[atom]*minimum+[tail]])
                sequence.append(atom)
            alternatives.append(tuple(sequence))
            if self._peek()!='|':break
            self._take('|')
        return tuple(alternatives)

    def accepts(self, text: str, *, root: str='root') -> bool:
        if root not in self.rules or len(text)>16_384:raise ValueError('Unknown root or oversized fixture')
        initial=('start',(root,),0,0);chart=[set() for _ in range(len(text)+1)];chart[0].add(initial)
        states=1
        for index in range(len(chart)):
            queue=deque(chart[index])
            def add(state,position=index):
                nonlocal states
                if state in chart[position]:return
                states+=1
                if states>1_000_000:raise ValueError('Grammar recognition state limit')
                chart[position].add(state)
                if position==index:queue.append(state)
            while queue:
                name,production,dot,start=queue.popleft()
                if dot==len(production):
                    for lhs,p,pos,origin in tuple(chart[start]):
                        if pos<len(p) and p[pos]==name:add((lhs,p,pos+1,origin))
                else:
                    symbol=production[dot]
                    if isinstance(symbol,str):
                        for p in self.rules[symbol]:add((symbol,p,0,index))
                        if symbol in self.nullable:add((name,production,dot+1,start))
                    elif index<len(text):
                        match=bool(self.classes[symbol.value].fullmatch(text[index])) if symbol.character_class else symbol.value==text[index]
                        if match:add((name,production,dot+1,start),index+1)
        return ('start',(root,),1,0) in chart[-1]
