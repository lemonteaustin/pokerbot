#!/usr/bin/env python3
"""Build the standalone page; no runtime dependencies or requests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    template = (ROOT / 'template.html').read_text()
    scripts = '\n\n'.join((ROOT / name).read_text() for name in ('bot.js', 'engine.js', 'presentation.js', 'ui.js'))
    assert '</script' not in scripts.lower()
    output = template.replace('/* INLINE_GAME */', scripts).replace('/* INLINE_STYLES */', (ROOT / 'style.css').read_text())
    (ROOT / 'index.html').write_text(output)
    print(f'Built demo/index.html ({len(output.encode()):,} bytes)')


if __name__ == '__main__':
    build()
