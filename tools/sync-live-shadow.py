#!/usr/bin/env python3
from __future__ import annotations
import hashlib, os, shutil, stat, subprocess, sys
from pathlib import Path

# The live session must keep Ubuntu's stock GDM resource. It is deliberately
# restored after this synchronizer as an additional safety barrier.
EXCLUDE_PREFIXES=(
    # Preserve live-only package/accounting state and installer plumbing.
    'var/lib/dpkg/',
    'var/lib/apt/',
    'etc/cloud/',
    'var/lib/cloud/',
    'usr/lib/systemd/user/ubuntu-desktop-installer.service',
    'etc/systemd/user/graphical-session.target.wants/ubuntu-desktop-installer.service',
    'usr/bin/subiquity-shell',
    'usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource',
    'usr/share/gnome-shell/gnome-shell-theme.gresource',
    'etc/alternatives/gdm3-theme.gresource',
)

def sig(p: Path):
    try: st=p.lstat()
    except FileNotFoundError: return None
    mode=stat.S_IFMT(st.st_mode)
    perms=stat.S_IMODE(st.st_mode)
    if stat.S_ISLNK(st.st_mode):
        return ('l',perms,os.readlink(p))
    if stat.S_ISREG(st.st_mode):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
        return ('f',perms,st.st_size,h.hexdigest())
    if stat.S_ISCHR(st.st_mode): return ('c',perms,st.st_rdev)
    if stat.S_ISBLK(st.st_mode): return ('b',perms,st.st_rdev)
    if stat.S_ISFIFO(st.st_mode): return ('p',perms)
    return ('o',mode,perms,st.st_size)

def leaves(root: Path):
    out=[]
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
        bp=Path(base)
        # Symlinked dirs appear in dirs; treat them as leaves.
        keep=[]
        for d in dirs:
            p=bp/d
            if p.is_symlink(): out.append(p.relative_to(root))
            else: keep.append(d)
        dirs[:] = keep
        out += [(bp/f).relative_to(root) for f in files]
    return out

def lexists(p: Path):
    return os.path.lexists(p)

def main():
    if len(sys.argv)!=4:
        raise SystemExit('usage: sync-live-shadow.py <original-standard-upper> <modified-standard-upper> <live-upper>')
    original, modified, live=map(Path,sys.argv[1:])
    changed=[]; shadowed=[]
    for rel in leaves(modified):
        rs=rel.as_posix()
        if any(rs == pref.rstrip('/') or rs.startswith(pref) for pref in EXCLUDE_PREFIXES): continue
        if sig(modified/rel) != sig(original/rel):
            changed.append(rel)
            if lexists(live/rel): shadowed.append(rel)
    # Deletions are rare in this build. Report them so they are visible rather
    # than pretending to have reconciled them.
    deleted=[rel for rel in leaves(original) if not lexists(modified/rel)]
    if deleted:
        print(f'WARN: {len(deleted)} standard-layer deletions detected; live layer keeps its own entries where present.')
    for rel in shadowed:
        src=modified/rel
        # rsync --relative preserves the path below modified and xattrs/ACLs.
        subprocess.run(['rsync','-aHAXR','--delete',str(modified)+'/./'+rel.as_posix(),str(live)+'/'],check=True)
    print(f'Live-layer reconciliation: {len(changed)} standard changes, {len(shadowed)} shadowed live paths synchronized.')

if __name__=='__main__': main()
