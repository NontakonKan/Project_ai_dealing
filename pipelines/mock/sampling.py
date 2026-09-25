"""helper สุ่มค่าแบบกำหนดสัดส่วน/ช่วง confidence"""


def pick_weighted(rng, dist):
    r, acc = rng.random(), 0.0
    for v, p in dist:
        acc += p
        if r <= acc:
            return v
    return dist[-1][0]


def conf(rng, lo=0.55, hi=0.95):
    return round(rng.uniform(lo, hi), 2)
