import collections
import inspect

class Reactive:
    """
    >>> r = Reactive(
    >>>     use_cache = True,  # cache intermediate values
    >>>     lazy_cache = True, # wait until use to calculate
    >>> )

    Assign constants:
    >>> r.a = 5
    >>> r.b = 2

    Or create and chain reactive components with position, keyword or implied.
    >>> r.c = r(lambda x, y, z: x*y + z + 1, 'a', y='b', z=0)
    >>> r.d = r(lambda b, a: a+b)

    Get as expected.
    >>> assert r.c == 11 (5*2 + 0 + 1)
    >>> assert r.d == 7 (5+2)

    Values will reactively update
    >>> r.a = 0
    >>> assert r.c == 1 (0*2 + 0 + 1)
    >>> assert r.d == 2 (0+2)

    Getitem, setitem, del and dir are also available
    >>> r['b'] = 3
    >>> assert r['b'] == 3
    >>> del r['c']
    >>> del r.d
    >>> assert sorted(dir(r)) == ['a', 'b']
    """
    def __init__(self, use_cache=True, lazy_cache=True):
        s = super().__setattr__
        s('_vals', {})
        s('_use_cache', use_cache)
        s('_lazy_cache', lazy_cache)
        s('_cache', {})
        s('_depends', collections.defaultdict(set))
        s('_depended', collections.defaultdict(set))

    def _update_cache(self, name, val, dep):
        assert all(x[0] == self for x in dep)
        dep = set([x[1] for x in dep])
        self._cache[name] = val
        for other in self._depends[name]:
            self._depended[other].remove(name)
        self._depends[name] = dep
        for other in dep:
            self._depended[other].add(name)

    def _invalidate_cache(self, name):
        if name in self._cache:
            del self._cache[name]
        for other in self._depended[name]:
            self._invalidate_cache(other)
        if name in self._depended:
            del self._depended[name]
        if name in self._depends:
            del self._depends[name]

    def __getattr__(self, name):
        if self._use_cache and name in self._cache:
            return self._cache[name]
        try:
            val = self._vals[name]
        except KeyError as e:
            raise AttributeError from e
        if isinstance(val, ReactiveObject):
            val, dep = val._compute()
            self._update_cache(name, val, dep)
        return val

    def __setattr__(self, name, value):
        self._invalidate_cache(name)
        self._vals[name] = value
        if self._use_cache and not self._lazy_cache:
            self.__getattr__(name)

    def __delattr__(self, name):
        self._invalidate_cache(name)
        del self._vals[name]

    def __dir__(self):
        return list(self._vals.keys())

    __getitem__ = __getattr__
    __setitem__ = __setattr__
    __delitem__ = __delattr__

    def __call__(self, function, *args, **kwargs):
        required_args = [x for x in inspect.getfullargspec(function)[0] if
                         x != 'self']
        required_args = required_args[len(args):]
        required_args = [x for x in required_args if not x in kwargs]
        kwargs = {**kwargs, **{x: x for x in required_args}}
        args = [ReactiveGetter(self, x) if isinstance(x, str) else x for x in args]
        kwargs = {k: ReactiveGetter(self, v) if isinstance(v, str) else v for k, v in
                  kwargs.items()}
        return ReactiveOp(function, '', *args, **kwargs)


class ReactiveObject:
    def _compute():
        raise NotImplementedError


class ReactiveGetter(ReactiveObject):
    def __init__(self, obj, name):
        self._obj = obj
        self._name = name

    def _compute(self):
        return (getattr(self._obj, self._name),
                set([(self._obj, self._name)]))


class ReactiveOp(ReactiveObject):
    def __init__(self, obj, call, *args, **kwargs):
        self._obj = obj
        self._call = call
        self._args = args
        self._kwargs = kwargs

    def _compute(self):
        args = [x for x in self._args]
        kwargs = self._kwargs.copy()
        depend = set()
        for i in range(len(args)):
            if isinstance(args[i], ReactiveObject):
                args[i], dep = args[i]._compute()
                depend |= dep
        for k in kwargs:
            if isinstance(kwargs[k], ReactiveObject):
                kwargs[k], dep = kwargs[k]._compute()
                depend |= dep
        obj = self._obj
        if isinstance(obj, ReactiveObject):
            obj, dep = obj._compute()
            depend |= dep
        if self._call == '':
            return obj(*args, **kwargs), depend
        else:
            return getattr(obj, self._call)(*args, **kwargs), depend
