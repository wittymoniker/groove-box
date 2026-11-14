"""update_signing.py — GROOVEBOX_R32_SIGNED_UPDATES_20261110

Signed update packages for sOS / Groovebox.  Pure Python Ed25519 (RFC 8032), so it runs in
the initramfs and on any desktop without extra packages.

    python3 update_signing.py keygen  [KEYDIR]         -> groovebox-update.key / .pub (hex)
    python3 update_signing.py sign    PACKAGE [KEY]    -> PACKAGE.sig
    python3 update_signing.py verify  PACKAGE [SIG] [PUB]   exit 0 = valid
    python3 update_signing.py status                    which public key is enforced

Signature = Ed25519 over  b"GROOVEBOX-UPDATE-V1\\0" + SHA-512(package bytes) + file name.
Policy (applied by sos-preboot-update and the in-app "Update code from USB now"):
  * a trusted public key is installed  -> only packages with a valid .sig are applied
  * no trusted key installed yet        -> legacy unsigned updates still apply (warned), so
    builds made before you created a key keep working.  Installing a key closes this.
Trusted public keys are looked up outside the app folder (an update cannot replace them):
  /etc/groovebox/update-signing.pub, /var/lib/groovebox-system/update-signing.pub
"""
from __future__ import annotations

import hashlib
import os
import sys

# ---------------------------------------------------------------- Ed25519 (RFC 8032) ----
_p = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_d = (-121665 * pow(121666, _p - 2, _p)) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _xrecover(y):
    xx = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p)
    x = pow(xx, (_p + 3) // 8, _p)
    if (x * x - xx) % _p:
        x = (x * _I) % _p
    if x % 2:
        x = _p - x
    return x


_By = (4 * pow(5, _p - 2, _p)) % _p
_B = (_xrecover(_By), _By, 1, (_xrecover(_By) * _By) % _p)      # extended coordinates


def _add(P, Q):
    x1, y1, z1, t1 = P; x2, y2, z2, t2 = Q
    a = (y1 - x1) * (y2 - x2) % _p; b = (y1 + x1) * (y2 + x2) % _p
    c = 2 * t1 * t2 * _d % _p; dd = 2 * z1 * z2 % _p
    e, f, g, h = b - a, dd - c, dd + c, b + a
    return (e * f % _p, g * h % _p, f * g % _p, e * h % _p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P); s >>= 1
    return Q


def _encode(P):
    x, y, z, _t = P
    zi = pow(z, _p - 2, _p); x = x * zi % _p; y = y * zi % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decode(s):
    if len(s) != 32:
        raise ValueError("bad point")
    y = int.from_bytes(s, "little"); sign = y >> 255; y &= (1 << 255) - 1
    if y >= _p:
        raise ValueError("bad point")
    x = _xrecover(y)
    if (x * x * _d * y * y - y * y + x * x + 1) % _p:      # -x²+y² = 1+d x²y²
        raise ValueError("not on curve")
    if (x & 1) != sign:
        x = _p - x
    return (x, y, 1, x * y % _p)


def _H(m):
    return hashlib.sha512(m).digest()


def _secret_expand(sk):
    h = _H(sk)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8; a |= 1 << 254
    return a, h[32:]


def public_key(sk):
    a, _ = _secret_expand(sk)
    return _encode(_mul(a, _B))


def sign(sk, msg):
    a, prefix = _secret_expand(sk)
    A = _encode(_mul(a, _B))
    r = int.from_bytes(_H(prefix + msg), "little") % _L
    R = _encode(_mul(r, _B))
    k = int.from_bytes(_H(R + A + msg), "little") % _L
    return R + int.to_bytes((r + k * a) % _L, 32, "little")


def verify(pk, msg, sig):
    try:
        if len(sig) != 64:
            return False
        A = _decode(pk); R = _decode(sig[:32])
        s = int.from_bytes(sig[32:], "little")
        if s >= _L:
            return False
        k = int.from_bytes(_H(sig[:32] + pk + msg), "little") % _L
        return _encode(_mul(s, _B)) == _encode(_add(R, _mul(k, A)))
    except Exception:
        return False


# ---------------------------------------------------------------- packages ---------------
MAGIC = b"GROOVEBOX-UPDATE-V1\0"
TRUSTED = ("/etc/groovebox/update-signing.pub", "/var/lib/groovebox-system/update-signing.pub")


def _digest(path):
    h = hashlib.sha512()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return MAGIC + h.digest() + os.path.basename(path).encode("utf-8")


def _read_hex(path):
    with open(path, encoding="ascii") as f:
        return bytes.fromhex(f.read().split()[0])


def default_keydir():
    return os.path.join(os.path.expanduser("~"), ".config", "groovebox-signing")


def keygen(keydir=None):
    keydir = keydir or default_keydir()
    os.makedirs(keydir, exist_ok=True)
    try:
        os.chmod(keydir, 0o700)
    except Exception:
        pass
    kp = os.path.join(keydir, "groovebox-update.key"); pp = os.path.join(keydir, "groovebox-update.pub")
    if not os.path.exists(kp):
        sk = os.urandom(32)
        fd = os.open(kp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(sk.hex() + "\n")
    sk = _read_hex(kp)
    with open(pp, "w", encoding="utf-8") as f:
        f.write(public_key(sk).hex() + "\n")
    return kp, pp


def sign_package(pkg, key=None):
    key = key or os.path.join(default_keydir(), "groovebox-update.key")
    sk = _read_hex(key)
    sig = sign(sk, _digest(pkg))
    out = pkg + ".sig"
    with open(out, "w", encoding="utf-8") as f:
        f.write(sig.hex() + "\n")
    return out


def trusted_keys():
    keys = []
    for p in TRUSTED:
        try:
            keys.append((p, _read_hex(p)))
        except Exception:
            pass
    return keys


def check_package(pkg, sig=None, pub=None):
    """(ok, message).  Applies the policy described in the module docstring."""
    keys = [(pub, _read_hex(pub))] if pub else trusted_keys()
    sig = sig or pkg + ".sig"
    if not keys:
        return True, "no trusted update key installed: unsigned update allowed (legacy). Install one to enforce signatures."
    if not os.path.isfile(sig):
        return False, "REFUSED: %s has no signature (%s) and a trusted update key is installed" % (os.path.basename(pkg), os.path.basename(sig))
    try:
        s = _read_hex(sig)
    except Exception:
        return False, "REFUSED: unreadable signature file %s" % sig
    msg = _digest(pkg)
    for path, k in keys:
        if verify(k, msg, s):
            return True, "signature valid (key %s, %s…)" % (path, k.hex()[:16])
    return False, "REFUSED: signature does not match any trusted update key"


def status():
    ks = trusted_keys()
    if not ks:
        return "Signed updates: no trusted key installed (unsigned updates still accepted)."
    return "Signed updates ENFORCED with: " + ", ".join("%s (%s…)" % (p, k.hex()[:16]) for p, k in ks)


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    cmd = argv[1]
    if cmd == "keygen":
        kp, pp = keygen(argv[2] if len(argv) > 2 else None)
        print("private key: %s (keep secret, back up)\npublic key:  %s\ninstall the public key on a device:\n"
              "  sudo install -D -m 0644 %s /etc/groovebox/update-signing.pub" % (kp, pp, pp))
        return 0
    if cmd == "sign" and len(argv) > 2:
        print(sign_package(argv[2], argv[3] if len(argv) > 3 else None)); return 0
    if cmd == "verify" and len(argv) > 2:
        ok, msg = check_package(argv[2], argv[3] if len(argv) > 3 else None, argv[4] if len(argv) > 4 else None)
        print(msg); return 0 if ok else 1
    if cmd == "status":
        print(status()); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
