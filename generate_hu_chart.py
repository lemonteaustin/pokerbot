#!/usr/bin/env python3
"""Offline import of public numeric no-ante heads-up push/fold chart data.

curl -fsSL https://www.holdemresources.net/hune | python3 generate_hu_chart.py
This preparation tool reads HTML on stdin. The bot uses only the saved dicts.
"""
from html.parser import HTMLParser
from pathlib import Path
import sys

SOURCE = 'https://www.holdemresources.net/hune'
RANKS = 'AKQJT98765432'


class ChartParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.rows, self.row, self.cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'table' and dict(attrs).get('class') == 'table handgrid':
            self.rows = []
        elif self.rows is not None:
            if tag == 'tr':
                self.row = []
            elif tag in ('th', 'td'):
                self.cell = ''

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if self.rows is None:
            return
        if tag in ('th', 'td') and self.cell is not None:
            self.row.append(self.cell.strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if len(self.row) == 14 and len(self.row[0]) == 1 and self.row[0] in RANKS:
                self.rows.append(self.row)
            self.row = None
        elif tag == 'table':
            self.tables.append(self.rows)
            self.rows = None


def convert(rows):
    assert len(rows) == 13
    result = {}
    for i, row in enumerate(rows):
        assert row[0] == RANKS[i]
        for j, value in enumerate(row[1:]):
            hand = (RANKS[i] * 2 if i == j else
                    RANKS[i] + RANKS[j] + 's' if i < j else
                    RANKS[j] + RANKS[i] + 'o')
            result[hand] = 0.0 if '*' in value else float(value.rstrip('+'))
    return result


def main():
    parser = ChartParser()
    parser.feed(sys.stdin.read())
    assert len(parser.tables) >= 2
    push, call = map(convert, parser.tables[:2])
    text = ['"""Numeric no-ante HU chart from HoldemResources.',
            f'Source: {SOURCE}',
            'Simplified equilibrium thresholds, capped at 20 BB. Not a multiway solution.',
            'Generated offline; no network or parsing at bot runtime.', '"""',
            f'SOURCE = {SOURCE!r}', 'PUSH_LIMITS = {']
    text.extend(f'    {k!r}: {v!r},' for k, v in sorted(push.items()))
    text.extend(['}', 'CALL_LIMITS = {'])
    text.extend(f'    {k!r}: {v!r},' for k, v in sorted(call.items()))
    text.extend(['}', "PUSH_INTERVALS = {'63s': ((0, 2.3), (5.1, 7.1)),",
                 "                  '53s': ((0, 2.4), (3.8, 12.9)),",
                 "                  '43s': ((0, 2.2), (4.9, 10.0))}", ''])
    Path('hu_nash.py').write_text('\n'.join(text))
    print('Saved 169 push and 169 call thresholds, plus three nonmonotone intervals.')


if __name__ == '__main__':
    main()
