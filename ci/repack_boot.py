#!/usr/bin/env python3
"""
repack_boot.py - orijinal boot.img icindeki kerneli yenisiyle degistirir.

Kullanim:
    python3 ci/repack_boot.py <orijinal_boot.img> <Image.gz-dtb> <cikti.img>

Davranis:
  * Android boot header v0/v1/v2 desteklenir (kobe2: v2, page size 2048).
  * Header (cmdline, adresler, os_version), ramdisk, second, recovery_dtbo
    ve dtb bolumleri oldugu gibi korunur; sadece kernel degisir.
  * Cikti, orijinal dosyayla ayni boyutta (bolum boyutu) sifirla doldurulur.
  * AVB footer (orijinalde varsa) atilir; yeni kernelle imza zaten
    gecersiz olacagindan footer'i tasimanin anlami yok.
  * Header'daki id (sha1) mkbootimg ile ayni yontemle yeniden hesaplanir.
"""
import hashlib
import struct
import sys


def pad(n, page):
    return (n + page - 1) // page * page


def parse(d):
    if d[:8] != b"ANDROID!":
        raise SystemExit("HATA: ANDROID! magic yok, bu bir boot.img degil")
    (ksz, kaddr, rsz, raddr, ssz, saddr, tags, page, hv, osv) = struct.unpack("<10I", d[8:48])
    h = dict(ksz=ksz, kaddr=kaddr, rsz=rsz, raddr=raddr, ssz=ssz, saddr=saddr,
             tags=tags, page=page, hv=hv, osv=osv, rdsz=0, rdoff=0, hsz=0, dsz=0)
    if hv >= 1:
        h["rdsz"], h["rdoff"], h["hsz"] = struct.unpack("<IQI", d[1632:1648])
    if hv >= 2:
        h["dsz"] = struct.unpack("<I", d[1648:1652])[0]
    return h


def sections(d, h):
    p = h["page"]
    off = p
    k = d[off:off + h["ksz"]]; off += pad(h["ksz"], p)
    r = d[off:off + h["rsz"]]; off += pad(h["rsz"], p)
    s = d[off:off + h["ssz"]]; off += pad(h["ssz"], p)
    rd = d[off:off + h["rdsz"]]; off += pad(h["rdsz"], p)
    dtb = d[off:off + h["dsz"]]; off += pad(h["dsz"], p)
    return k, r, s, rd, dtb, off


def boot_id(h, k, r, s, rd, dtb):
    sha = hashlib.sha1()
    for blob in (k, r, s):
        sha.update(blob); sha.update(struct.pack("<I", len(blob)))
    if h["hv"] >= 1:
        sha.update(rd); sha.update(struct.pack("<I", len(rd)))
    if h["hv"] >= 2:
        sha.update(dtb); sha.update(struct.pack("<I", len(dtb)))
    return sha.digest().ljust(32, b"\0")


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    stock_path, kernel_path, out_path = sys.argv[1:]
    d = open(stock_path, "rb").read()
    new_k = open(kernel_path, "rb").read()
    h = parse(d)
    k, r, s, rd, dtb, end = sections(d, h)

    hdr = bytearray(d[:h["page"]])
    struct.pack_into("<I", hdr, 8, len(new_k))        # kernel_size
    hdr[576:608] = boot_id(h, new_k, r, s, rd, dtb)   # id

    p = h["page"]
    body = bytes(hdr)
    for blob in (new_k, r, s, rd, dtb):
        body += blob + b"\0" * (pad(len(blob), p) - len(blob))

    if len(body) > len(d):
        raise SystemExit("HATA: yeni imaj (%d) bolum boyutundan (%d) buyuk" % (len(body), len(d)))
    out = body + b"\0" * (len(d) - len(body))
    open(out_path, "wb").write(out)

    print("stok kernel : %d bayt" % len(k))
    print("yeni kernel : %d bayt" % len(new_k))
    print("ramdisk/dtb : korundu (%d / %d bayt)" % (len(r), len(dtb)))
    print("cikti       : %s (%d bayt, bolum boyutu ile ayni)" % (out_path, len(out)))
    if d[-64:-60] == b"AVBf":
        print("not         : orijinaldeki AVB footer atildi (yeni kernelle imza gecersiz)")


if __name__ == "__main__":
    main()
