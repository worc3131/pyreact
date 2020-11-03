
import pytest

from reactpy import Reactive

@pytest.fixture
def r():
    return Reactive(verbose=True)

def test_basic1(r):
    r.a = 3
    r.b = r(lambda a: a+2)
    r.a = 5
    assert r.b == 7

def test_basic2(r):
    r.a = 3
    r.b = r(lambda a: a+2)
    assert r.b == 5
    r.a = 5
    assert r.b == 7

def test_basic3(r):
    r.a = 2
    r.b = 5
    r.c = r(lambda a, b: a*b)
    assert r.a == 2
    assert r.b == 5
    assert r.c == 10
    r.a = 3
    assert r.a == 3
    assert r.b == 5
    assert r.c == 15

def test_noargs(r):
    r.a = r(lambda: 5)
    assert r.a == 5

def test_args(r):
    r.a = 2
    r.b = 3
    r.c = r(lambda x, y: x-y, 'b', 'a')
    assert r.c == 1
    r.b = 5
    assert r.c == 3

def test_kwargs(r):
    r.a = 2
    r.b = 3
    r.c = r(lambda x, y: x//y, x='b', y='a')
    assert r.c == 1
    r.b = 7
    assert r.c == 3

def test_mixed_args(r):
    r.a = 2
    r.b = 3
    r.c = r(lambda a, x, y: a+x*y, x='b', y=5)
    assert r.c == 17
    r.b = 0
    assert r.c == 2

def test_fn(r):
    def f(a, b):
        return b-a
    r.a = 2
    r.b = 3
    r.c = r(f)
    assert r.c == 1
    r.a = 4
    assert r.c == -1
    r.d = r(f, a='b', b='a')
    assert r.d == 1
    r.a = 6
    assert r.d == 3
    r.d = r(f, 'a', 'c')
    assert r.d == -9

def test_class(r):
    class T:
        def __init__(self, x, y):
            self.z = y-x
    r.a = 2
    r.b = 3
    r.c = r(T, 'a', 'b')
    assert r.c.z == 1
    r.d = r(lambda x: T(x.z, x.z), 'c')
    assert r.d.z == 0

def test_get(r):
    r.a = 5
    r.b = r(lambda a: a+2)
    assert r['a'] == 5
    assert r['b'] == 7

def test_set(r):
    r['a'] = 5
    r['b'] = r(lambda a: a+2)
    assert r.a == 5
    assert r.b == 7

def test_missing(r):
    r.b = 5
    r.b
    with pytest.raises(AttributeError):
        r.a

def test_del(r):
    r.a = 2
    r.b = r(lambda a: a+2)
    r.a
    r.b
    del r.a
    with pytest.raises(AttributeError):
        r.a
    with pytest.raises(AttributeError):
        r.b  # checking cache invalidated
    r.a = 3
    r.b
    del r['b']
    with pytest.raises(AttributeError):
        r.b

def test_hasattr(r):
    r.a = 2
    r.b = r(lambda a: a+2)
    assert hasattr(r, 'a')
    assert hasattr(r, 'b')
    assert not hasattr(r, 'c')

def test_dir(r):
    r.a = 2
    r.b = 3
    assert sorted(dir(r)) == ['a', 'b']

def test_cyclic(r):
    r.a = 5
    r.b = r(lambda a, b: a+b)
    with pytest.raises(RecursionError):
        r.b

def test_cyclic_broken(r):
    r.a = r(lambda d: d+1)
    r.b = r(lambda a: a+1)
    r.c = r(lambda b: b+1)
    r.d = r(lambda c: c+1)
    r.b = 5
    assert r.b == 5
    assert r.c == 6
    assert r.d == 7
    assert r.a == 8

def test_cache(r):
    calls = 0
    def f(x):
        nonlocal calls
        calls += 1
        return calls
    r.a = 0
    r.b = r(f, x='a')
    assert r.b == 1
    r.c = r(lambda b: b+0)
    assert r.c == 1
    assert r.b == 1
    r.a = 1  # invalidate cache
    assert r.b == 2

def test_no_cache(r):
    r._set_options(use_cache=False)
    calls = 0
    def f(x):
        nonlocal calls
        calls += 1
        return calls
    r.a = 0
    r.b = r(f, x='a')
    assert r.b == 1
    r.c = r(lambda b: b+0)
    assert r.c == 2
    assert r.b == 3
    assert r.b == 4
    assert len(r._cache) == 0

def test_non_lazy_eval(r):
    r.a = r(lambda: 1/0)
    r._set_options(lazy_eval=False)
    with pytest.raises(ZeroDivisionError):
        r.a = r(lambda: 1/0)

def test_non_lazy_eval_child(r):
    r._set_options(lazy_eval=False)
    r.a = 5
    r.b = r(lambda a: 1/a)
    assert r.b == 0.2
    with pytest.raises(ZeroDivisionError):
        # error as when r.a is updated r.b is recalculated
        r.a = 0

def test_changes(r):
    r.a = 3
    r.b = r(lambda a: 10//a)
    r.c = r(lambda a, b: a+b)
    assert (r.a, r.b, r.c) == (3, 3, 6)
    r.a = 5
    assert (r.a, r.b, r.c) == (5, 2, 7)
    r.b = 10
    assert (r.a, r.b, r.c) == (5, 10, 15)
    r.a = r(lambda b: b + 3)
    assert (r.a, r.b, r.c) == (13, 10, 23)
    del r.a
    r.c = r(lambda b: b+2)
    r.a = 5
    assert (r.a, r.b, r.c) == (5, 10, 12)

def test_num_calls(r):
    calls = 0
    def count(b1, b2):
        nonlocal calls
        calls += 1
        return b1+b2
    r.a = 0
    r.b1 = r(lambda a: a+1)
    r.b2 = r(lambda a: a*2)
    r.c = r(count)
    r.d1 = r(lambda c: c+1)
    r.d2 = r(lambda c: 2*c)
    r.e = r(lambda d1, d2: d1+d2)

    assert r.e == 4
    assert calls == 1

    r.d1 = r(lambda c: c+2)
    assert r.e == 5
    assert calls == 1

    r.a = 1
    assert r.e == 14
    assert calls == 2

    r.c = r(count)
    assert r.e == 14
    assert calls == 3

    r.b1 = 0
    r.b2 = 1
    assert r.e == 5
    assert calls == 4

    r.d1 = r(lambda c: 0-c)
    r.d2 = r(lambda c: 0+c)
    assert r.e == 0
    assert calls == 4

def test_num_calls_non_lazy(r):
    r._set_options(lazy_eval=False)
    calls = 0
    def count(b1, b2):
        nonlocal calls
        calls += 1
        return b1+b2
    r.a = 0
    r.b1 = r(lambda a: a+1)
    r.b2 = r(lambda a: a*2)
    r.c = r(count)
    r.d1 = r(lambda c: c+1)
    r.d2 = r(lambda c: 2*c)
    r.e = r(lambda d1, d2: d1+d2)

    assert r.e == 4
    assert calls == 1

    r.d1 = r(lambda c: c+2)
    assert r.e == 5
    assert calls == 1

    r.a = 1
    assert r.e == 14
    assert calls == 2

    r.c = r(count)
    assert r.e == 14
    assert calls == 3

    r.b1 = 0
    r.b2 = 1
    assert r.e == 5
    assert calls == 5

    r.d1 = r(lambda c: 0-c)
    r.d2 = r(lambda c: 0+c)
    assert r.e == 0
    assert calls == 5

def test_num_calls_no_cache(r):
    r._set_options(lazy_eval=False, use_cache=False)
    calls = 0
    def count(b1, b2):
        nonlocal calls
        calls += 1
        return b1+b2
    r.a = 0
    r.b1 = r(lambda a: a+1)
    r.b2 = r(lambda a: a*2)
    r.c = r(count)
    r.d1 = r(lambda c: c+1)
    r.d2 = r(lambda c: 2*c)
    r.e = r(lambda d1, d2: d1+d2)

    assert r.e == 4
    assert calls == 7  # each time something is added & down each branch

    r.d1 = r(lambda c: c+2)
    assert r.e == 5
    assert calls == 11

    r.a = 1
    assert r.e == 14
    assert calls == 15
