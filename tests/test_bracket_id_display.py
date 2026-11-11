import copy
import json
import unittest

from prompt_builder.presentation import render


def read_display(text):
    """Independent test reader: ID-keyed brackets become arrays, braces objects."""
    decoder=json.JSONDecoder()
    def skip(pos):
        while pos<len(text) and text[pos].isspace():pos+=1
        return pos
    def read(pos):
        pos=skip(pos)
        if text[pos] not in '[{':return decoder.raw_decode(text,pos)
        is_array=text[pos]=='[';close=']' if is_array else '}';pos=skip(pos+1)
        result=[] if is_array else {}
        if text[pos]==close:return result,pos+1
        while True:
            key,pos=decoder.raw_decode(text,pos)
            if not isinstance(key,str):raise ValueError('Display key is not a string')
            pos=skip(pos)
            if text[pos]!=':':raise ValueError('Missing colon')
            value,pos=read(pos+1)
            if is_array:result.append(value)
            else:result[key]=value
            pos=skip(pos)
            if text[pos]==close:return result,pos+1
            if text[pos]!=',':raise ValueError('Missing separator')
            pos=skip(pos+1)
    result,pos=read(0)
    if skip(pos)!=len(text):raise ValueError('Unconsumed text')
    return result


class BracketIdentityDisplayTests(unittest.TestCase):
    def test_exact_user_requested_example(self):
        data={'items':[{'id':'a','count':2}],'empty':[],'object':{}}
        identities=[{'path':['items'],'id_field':'id'},{'path':['empty'],'id_field':None}]
        self.assertEqual(render(data,'id_keyed_arrays',identities),'''{
  "items": [
    "a": {
      "id": "a",
      "count": 2
    }
  ],
  "empty": [],
  "object": {}
}''')

    def test_nested_escaped_data_round_trips_without_metadata_fields(self):
        identity='a"\\\n]: {},雪'
        data={'rows.list':[{'sku':identity,'values':['',None,False,7,2.5,'[x]: {y}'],
                            '$array':{'$object':'literal'},'children':[{'code':'z','empty':[]}]}]}
        identities=[{'path':['rows.list'],'id_field':'sku'},
                    {'path':['rows.list',None,'values'],'id_field':None},
                    {'path':['rows.list',None,'children'],'id_field':'code'},
                    {'path':['rows.list',None,'children',None,'empty'],'id_field':'future'}]
        original=copy.deepcopy((data,identities))
        text=render(data,'id_keyed_arrays',identities)
        self.assertEqual(read_display(text),data)
        self.assertEqual((data,identities),original)
        self.assertIn(json.dumps(identity,ensure_ascii=False)+': {',text)
        self.assertIn('"null": null',text)
        self.assertIn('"false": false',text)
        self.assertIn('"7": 7',text)
        self.assertIn('"2.5": 2.5',text)
        self.assertEqual(text.count('"$array"'),1)
        self.assertEqual(text.count('"$object"'),1)

    def test_root_arrays_empty_containers_and_scalar_types(self):
        for data,identities in [([], [{'path':[],'id_field':None}]),({},[]),('text',[]),
                                ([1,True,None,'a'],[{'path':[],'id_field':None}]),
                                ([{'uid':'a','nested':{}}],[{'path':[],'id_field':'uid'}])]:
            with self.subTest(data=data):
                self.assertEqual(read_display(render(data,'id_keyed_arrays',identities)),data)
        self.assertEqual(render([],'id_keyed_arrays',[{'path':[],'id_field':None}]),'[]')
        self.assertEqual(render({},'id_keyed_arrays',[]),'{}')

    def test_only_id_display_is_non_json(self):
        data={'items':['a']};mapping=[{'path':['items'],'id_field':None}]
        self.assertEqual(json.loads(render(data,'normal_json')),data)
        with self.assertRaises(json.JSONDecodeError):json.loads(render(data,'id_keyed_arrays',mapping))
        self.assertEqual(render(data,'full_paths',mapping),'<root>: <object>\nitems: <array>\nitems.a: "a"')


if __name__=='__main__':unittest.main()
