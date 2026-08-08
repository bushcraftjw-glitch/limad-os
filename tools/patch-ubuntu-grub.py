#!/usr/bin/env python3
from __future__ import annotations
import re, sys
from pathlib import Path

NORMAL_TITLE = 'LiMaD OS starten oder installieren'
SAFE_TITLE = 'LiMaD OS - Safe Graphics'


def menu_blocks(lines):
    blocks=[]
    i=0
    while i < len(lines):
        if re.match(r'^\s*menuentry\s+', lines[i]):
            start=i
            depth=lines[i].count('{')-lines[i].count('}')
            i += 1
            while i < len(lines) and depth > 0:
                depth += lines[i].count('{')-lines[i].count('}')
                i += 1
            blocks.append((start,i))
        else:
            i += 1
    return blocks


def ensure_nomodeset(block):
    out=[]
    for line in block:
        if re.match(r'^\s*linux(?:efi)?\s+/casper/vmlinuz\b', line) and 'nomodeset' not in line:
            parts=line.split()
            try:
                idx=next(i for i,p in enumerate(parts) if p.endswith('/casper/vmlinuz'))
                parts.insert(idx+1,'nomodeset')
                indent=re.match(r'^\s*',line).group(0)
                line=indent+' '.join(parts)+'\n'
            except StopIteration:
                pass
        out.append(line)
    return out


def rename_menuentry(line,title):
    # Preserve any options/classes after the quoted title.
    m=re.match(r"^(\s*menuentry\s+)(['\"])(.*?)(\2)(.*)$",line.rstrip('\n'))
    if not m:
        return line
    return f"{m.group(1)}{m.group(2)}{title}{m.group(4)}{m.group(5)}\n"


def patch(text):
    lines=text.splitlines(True)
    saw_timeout=False
    saw_style=False
    for i,line in enumerate(lines):
        if re.match(r'^\s*set\s+timeout_style=',line):
            indent=re.match(r'^\s*',line).group(0)
            lines[i]=indent+'set timeout_style=menu\n'; saw_style=True
        elif re.match(r'^\s*set\s+timeout=',line):
            indent=re.match(r'^\s*',line).group(0)
            lines[i]=indent+'set timeout=10\n'; saw_timeout=True
    if not (saw_timeout and saw_style):
        first_menu=next((i for i,l in enumerate(lines) if re.match(r'^\s*menuentry\s+',l)),len(lines))
        inject=[]
        if not saw_style: inject.append('set timeout_style=menu\n')
        if not saw_timeout: inject.append('set timeout=10\n')
        lines[first_menu:first_menu]=inject

    # First pass: rename known Ubuntu entries.
    for i,line in enumerate(lines):
        if re.match(r'^\s*menuentry\s+',line):
            low=line.lower()
            if 'safe graphics' in low:
                lines[i]=rename_menuentry(line,SAFE_TITLE)
            elif 'try or install ubuntu' in low or ('install ubuntu' in low and 'safe graphics' not in low):
                lines[i]=rename_menuentry(line,NORMAL_TITLE)

    blocks=menu_blocks(lines)
    normal=None; safe=None
    for start,end in blocks:
        head=lines[start].lower()
        if SAFE_TITLE.lower() in head or 'safe graphics' in head:
            safe=(start,end)
        elif NORMAL_TITLE.lower() in head or 'try or install ubuntu' in head:
            normal=(start,end)

    # If the source ISO has a safe entry, harden it with nomodeset.
    if safe:
        start,end=safe
        lines[start:end]=ensure_nomodeset(lines[start:end])
    elif normal:
        # Ubuntu normally ships one, but create it deterministically if not.
        start,end=normal
        clone=list(lines[start:end])
        clone[0]=rename_menuentry(clone[0],SAFE_TITLE)
        clone=ensure_nomodeset(clone)
        lines[end:end]=['\n']+clone

    out=''.join(lines)
    if NORMAL_TITLE not in out:
        raise SystemExit('normal LiMaD boot entry missing after patch')
    if SAFE_TITLE not in out:
        raise SystemExit('safe graphics boot entry missing after patch')
    # Verify safe menu contains nomodeset.
    lines=out.splitlines(True)
    for start,end in menu_blocks(lines):
        if SAFE_TITLE.lower() in lines[start].lower():
            if not any('nomodeset' in l for l in lines[start:end] if re.match(r'^\s*linux(?:efi)?\s+',l)):
                raise SystemExit('safe graphics entry lacks nomodeset')
            break
    if 'set timeout=10' not in out or 'set timeout_style=menu' not in out:
        raise SystemExit('visible boot menu timeout missing')
    return out


def main():
    if len(sys.argv)!=2:
        raise SystemExit('usage: patch-ubuntu-grub.py <grub.cfg>')
    p=Path(sys.argv[1])
    p.write_text(patch(p.read_text(encoding='utf-8')),encoding='utf-8')

if __name__=='__main__': main()
