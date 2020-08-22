import io

bti = lambda bytes_: int.from_bytes(bytes_, "little")
itb = lambda int_, length = 2: int_.to_bytes(length, "little")

class riff_chunk:
    cid=b""
    size=0
    extra=b""
    offset=0
    hsize=8
    cht=[]
    mod=False
    data=b''
    def __init__(self, cid, size, hsize=8, extra=None, offset=0, cht=[], mod=False, data=None):
        self.cid=cid
        self.size=size
        self.extra=extra
        self.offset=offset
        self.hsize=hsize
        self.cht=cht
        self.mod=mod
        self.data=data

class riff_path:
    etp=None
    ep=None
    ebl=None
    p=[]

    def __init__(self, top, parr):
        self.etp=top
        self.p=parr
        lf=len(parr)
        if lf > 1:
            self.ep=self.get_block(lf-2)
        else:
            self.ep=top
        self.ebl=self.get_block(lf-1)

    def get_block(self, pos):
        tp=self.p[:pos+1]
        nbl=self.etp
        for i in tp:
            nbl=nbl.cht[i]
        return nbl

    def update_path_sz(self, nsz):
        diff=nsz-self.ebl.size
        barr=[self.get_block(bp) for bp in range(len(self.p))]
        barr.insert(0, self.etp)
        for i in barr:
            i.size+=diff

    def add_header_size(self, _hsize=8):
        barr=[self.get_block(bp) for bp in range(len(self.p))]
        barr.insert(0, self.etp)
        for i in barr:
            i.size+=_hsize

    def set_path_mod(self, boo):
        barr=[self.get_block(bp) for bp in range(len(self.p))]
        barr.insert(0, self.etp)
        for i in barr:
            i.mod=boo

class __w:
    p=None

def is_riff(fs):
    fs.seek(0)
    h=fs.read(4)
    if h != b"RIFF":
        return False
    return True
    
def get_chunk(fs, off=0):
    fs.seek(off)
    h=fs.read(4)
    fss=bti(fs.read(4))
    ack=riff_chunk(h, fss)
    ack.offset=off+8
    if h == b"RIFF" or h == b"LIST":
        ack.extra=fs.read(4)
        ack.offset+=4
        ack.hsize+=4
    return ack

def get_riff(fs):
    if not is_riff(fs):
        raise ValueError("Invalid RIFF file")
        return None
    off=__w()
    off.p=0
    return _get_level(fs, off)
    
def _get_level(fs, off, size=None, parent=None):
    if size == None and parent == None:
        p=get_chunk(fs)
        off.p+=p.hsize
        _get_level(fs, off, p.size, p) # Sets .cht
        return p
    roff=4 # Why 4? Because the extra 4 bytes on the parent ck are included in size
    arr=[]

    while roff < size:
        ck=get_chunk(fs, off.p)
        off.p += ck.hsize
        if ck.cid == b"RIFF" or ck.cid == b"LIST": # Inception
            _get_level(fs, off, ck.size, ck) # Sets ck.cht
        else:
            off.p   += ck.size
        arr.append(ck)
        roff    += ck.hsize+ck.size
    parent.cht=arr
    return arr

def get_metadata(fs, l):
    if l.cid != b"LIST" or l.extra != b"INFO":
        raise ValueError("Bad metadata block")
        return
    m=dict()
    for i in l.cht:
        fs.seek(i.offset)
        m[i.cid] = fs.read(i.size)
    return m


def path_to_metadata(pbl, new=False):
    bl=pbl.ebl
    cc=[]
    for c in range(len(bl.cht)):
        if bl.cht[c].cid == b"LIST" and bl.cht[c].extra == b"INFO":
            cc.append(c)
    if cc == []:
        if new:
            nbl=riff_chunk(b"LIST", 4, hsize=12, extra=b"INFO", mod=True)
            cc.append(len(pbl.ebl.cht))
            pbl.ebl.cht.append(nbl)
            pbl.add_header_size(_hsize=12) # 8 in normal cases, here we include size
            pbl.set_path_mod(True)
        else:
            raise ValueError("Metadata block not found")
            return
    return riff_path(bl, cc)


def set_metadata(bpath, di, nullc=False):
    bl=bpath.ebl
    if bl.cid != b'LIST' or bl.extra != b'INFO':
        raise ValueError("Bad metadata block")
        return
    arr=[]
    acsz=0
    for a in di:
        aa = a[:4]
        if len(di[a])%2 or nullc:
            di[a] += b'\x00'
        arr.append(riff_chunk(aa, len(di[a]), mod=True, data=di[a]))
        acsz+=8+len(di[a])
    acsz+=4
    bl.mod=True
    bl.cht=arr
    bpath.update_path_sz(acsz) # bl.size+=(diff of acsz) for everyone
    bpath.set_path_mod(True)

def save_riff(fs, bfs, bl):
    fs.write(bl.cid)
    fs.write(itb(bl.size, length=4))
    if bl.mod:
        if bl.cid == b"RIFF" or bl.cid == b"LIST":
            if bl.data == None:
                fs.write(bl.extra)
                for i in bl.cht:
                    save_riff(fs, bfs, i)
            else:
                fs.write(bl.data)
        else:
            fs.write(bl.data)
    else:
        if bl.cid == b"RIFF" or bl.cid == b"LIST":
            fs.write(bl.extra)
            bfs.seek(bl.offset)
            fs.write(bfs.read(bl.size-4))
        else:
            bfs.seek(bl.offset)
            fs.write(bfs.read(bl.size))
