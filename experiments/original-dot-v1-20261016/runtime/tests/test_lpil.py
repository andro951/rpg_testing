import unittest
from optimization import lpil
from optimization.prompt_builder import validate_task, validate_replacements, parse_output
from optimization.templates import render


class LPILTests(unittest.TestCase):
    def test_literal_nesting_matches_all_five_supplied_examples(self):
        cases = {'<|hello|>': '`hello`', '<|<|hello|>|>': '`<|hello|>`',
                 '<|(1|hello|)|>': '`(1|hello|)`', '(1|(1|hello|)|)': '(1|(1|hello|)|)',
                 '(1|hello|)': '(1|hello|)'}
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(lpil.normalize(source), expected)

    def test_exactly_one_level_change_before_separate_normalization(self):
        text = '(2|hello|) (2{name})\n(2:TITLE:Background:)\n(2(BLOCK))\ntext\n(2(/BLOCK))\n'
        expected = '(1|hello|) (1{name})\n(1:TITLE:Background:)\n(1(BLOCK))\ntext\n(1(/BLOCK))\n'
        self.assertEqual(lpil.lower_level(text), expected)
        self.assertEqual(lpil.lower_level('(1|hello|)'), '<|hello|>')
        self.assertEqual(lpil.normalize(lpil.lower_level('(1|hello|)')), '`hello`')
        self.assertEqual(lpil.lower_level('(1{name})'), '<{name}>')
        self.assertEqual(lpil.raise_level(expected), text)

    def test_nested_markers_shift_once_each(self):
        self.assertEqual(lpil.lower_level('(2|(1|hello|)|)'), '(1|<|hello|>|)')
        self.assertEqual(lpil.normalize(lpil.lower_level('(2|(1|hello|)|)')), '(1|<|hello|>|)')

    def test_raising_handwritten_backticks_and_deferred_markers(self):
        self.assertEqual(lpil.raise_level('`hello` <{name}> (2{name})'), '(1|hello|) (1{name}) (3{name})')
        self.assertEqual(lpil.normalize('Before `hello` after.'), 'Before `hello` after.')
        self.assertEqual(lpil.lower_level('Before `hello` after.'), 'Before `hello` after.')

    def test_named_blocks_nest_and_preserve_content_whitespace(self):
        text = '--- A ---\r\n<(OUTER)>\r\n  hello\r\n<(INNER)>\r\n\r\nworld\r\n<(/INNER)>\r\n<(/OUTER)>\r\n'
        self.assertEqual(lpil.content(text), '  hello\r\n\r\nworld\r\n')
        self.assertEqual(lpil.lower_level(lpil.raise_level(text)), text)
        # Deferred metadata is content at the current level, not active metadata.
        self.assertEqual(lpil.content('(1:TITLE:Later:)\n'), '(1:TITLE:Later:)\n')

    def test_malformed_constructs_and_block_mismatch_report_errors(self):
        cases = ['<{unfinished', '<|unfinished', '(1|unfinished', '(0{name})', '(-1|text|)',
                 '<(A)>\n<(/B)>\n', '<(A)>\n', '<(/A)>\n', '(0:TITLE:Bad:)\n',
                 '<(A)>\n<(B)>\n<(/A)>\n<(/B)>\n']
        cases += ['<(BROKEN', 'before <(BLOCK)> after', '(-1(BLOCK))\n', '(1(BROKEN)\n']
        for text in cases:
            with self.subTest(text=text), self.assertRaises(lpil.SyntaxError):
                lpil.parse(text)

    def test_defined_generic_type_multiline_and_ordinary_parentheses(self):
        text = 'ordinary (notes) <:NOTE:first\nsecond:>'
        with self.assertRaisesRegex(lpil.SyntaxError, 'Define'):
            lpil.parse(text)
        self.assertEqual(lpil.lower_level(lpil.raise_level(text, types=['NOTE']), types=['NOTE']), text)
        self.assertEqual(lpil.normalize(text, types=['NOTE']), text)

    def test_lp_parser_has_no_task_output_requirement(self):
        self.assertEqual(lpil.normalize('Ordinary text.'), 'Ordinary text.')
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            validate_task('Ordinary task without a required output.')
        valid = '<(REQUIRED_OUTPUT)>\nOnly a category.\n<(/REQUIRED_OUTPUT)>\n'
        validate_task(valid)
        with self.assertRaises(ValueError):
            validate_task(valid + valid)

    def test_opaque_data_is_not_lowered_normalized_or_substituted(self):
        raw = 'literal (2{name}) <{name}> <|text|> `unclosed'
        fragments = {'SLOT': [lpil.Opaque(raw)]}
        self.assertEqual(lpil.assemble('(1:TITLE:Evidence:)\n<{SLOT}>', fragments), '--- Evidence ---\n' + raw)
        template = '<{state}> <{event}>'
        self.assertEqual(lpil.substitute(template, {'state': '<{event}>', 'event': raw}), '<{event}> ' + raw)

    def test_fragment_title_raised_then_lowered_once(self):
        fragments = {'SLOT': lpil.parse('--- Inner ---\n(1{name})\n')}
        self.assertEqual(lpil.assemble('(1:TITLE:Outer:)\n<{SLOT}>', fragments), '--- Outer ---\n--- Inner ---\n(1{name})\n')

    def test_counts_ignore_literal_references_and_deferred_markers(self):
        requirements = [{'name': 'x'}]
        validate_replacements('<{x}> `<{x}>` (1{x})', requirements)
        for text in ('', '<{x}><{x}>', '<{x}><{unknown}>'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_replacements(text, requirements)
        validate_replacements('no markers', [])
        validate_replacements('<{x}><{x}>', [{'name': 'x', 'count': 2}])
        for requirements in ([{'name': 'x', 'count': 0}], [{'name': 'x', 'count': True}], [{'name': 'x'}, {'name': 'x'}]):
            with self.assertRaises(ValueError):
                validate_replacements('', requirements)

    def test_standard_candidate_deferred_markers_empty_system_and_raw_data(self):
        config = {'use_standard_opro_output': True, 'new_replacements': [{'name': 'x'}]}
        text = 'SYSTEM_MESSAGE:\n\nUSER_MESSAGE:\n--- Input ---\n(1{x})'
        candidate = parse_output(text, config)
        self.assertEqual(candidate['system'], '')
        self.assertEqual(candidate['user'], '--- Input ---\n<{x}>')
        data = '<{x}> (1{x}) ${x} `unfinished'
        self.assertEqual(render(candidate, {'x': data}), [{'role': 'user', 'content': '--- Input ---\n' + data}])

    def test_new_candidates_reject_wrong_levels_repetition_missing_and_unknown(self):
        config = {'use_standard_opro_output': True, 'new_replacements': [{'name': 'x'}]}
        for marker in ('<{x}>', '(2{x})', '(1{x})(1{x})', '(1{unknown})', '`(1{x})`', '${x}'):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                parse_output('SYSTEM_MESSAGE:\n\nUSER_MESSAGE:\n' + marker, config)

    def test_custom_output_does_not_require_system_user_sections(self):
        config = {'use_standard_opro_output': False, 'new_replacements': [{'name': 'message'}]}
        self.assertEqual(parse_output('Classify (1{message})', config), 'Classify <{message}>')
        self.assertEqual(parse_output('Plain artifact.', {'use_standard_opro_output': False, 'new_replacements': []}), 'Plain artifact.')


if __name__ == '__main__':
    unittest.main()
