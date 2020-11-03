import collections
import inspect
import itertools

class Reactive:
    """
    >>> r = Reactive(
    >>>     use_cache = True, # cache intermediate values
    >>>     lazy_eval = True, # wait until use to calculate
    >>> )

    If use_cache and lazy_eval are both false, we still do full calculations on
    each update, so we can confirm that there are no exceptions.

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
    def __init__(self, use_cache=True, lazy_eval=True, verbose=False):
        s = super().__setattr__
        self._set_options(
            use_cache=use_cache,
            lazy_eval=lazy_eval,
            verbose=verbose,
        )
        self._clear()

    def _set_options(self, use_cache=None, lazy_eval=None, verbose=None):
        s = super().__setattr__
        if use_cache is not None:
            s('_use_cache', use_cache)
        if lazy_eval is not None:
            s('_lazy_eval', lazy_eval)
        if verbose is not None:
            s('_verbose', verbose)

    def _clear(self):
        s = super().__setattr__
        s('_vals', {})
        s('_cache', {})
        s('_depends', collections.defaultdict(set))
        s('_depended', collections.defaultdict(set))

    def _log(self, msg):
        print(msg)

    def _update_cache(self, name, val):
        if self._verbose:
            self._log(f'Update cache: {name}')
        if self._use_cache:
            self._cache[name] = val

    def _update_depends(self, name, dep):
        if self._verbose:
            self._log(f'Update depends: {name}')
        assert all(x[0] == self for x in dep)
        dep = set([x[1] for x in dep])
        self._set_depends(name, dep)

    def _invalidate_cache_depends(self, name):
        if self._verbose:
            self._log(f'Invalidate cache depends: {name}')
        self._invalidate_cache(name)
        self._set_depends(name, None)

    def _invalidate_cache(self, name):
        if self._verbose:
            self._log(f'Invalidate cache: {name}')
        if name in self._cache:
            del self._cache[name]
        for other in self._depended[name]:
            self._invalidate_cache(other)

    def _set_depends(self, name, depends):
        if self._verbose:
            self._log(f'Set depends: {name}')
        for other in self._depends[name]:
            self._depended[other].remove(name)
        if depends is None:
            del self._depends[name]
        else:
            self._depends[name] = depends
            for other in depends:
                self._depended[other].add(name)

    def __getattr__(self, name):
        if self._verbose:
            self._log(f'Get attr: {name}')
        if self._use_cache and name in self._cache:
            return self._cache[name]
        try:
            val = self._vals[name]
        except KeyError as e:
            raise AttributeError from e
        if isinstance(val, ReactiveObject):
            dep = val._get_depends()
            val = val._compute()
            self._update_cache(name, val)
            self._update_depends(name, dep)
        return val

    def __setattr__(self, name, value):
        if self._verbose:
            self._log(f'Set attr: {name}')
        self._invalidate_cache_depends(name)
        self._vals[name] = value
        if not self._lazy_eval:
            self._update(name)

    def _calculate_outer_branches(self, root):
        if self._verbose:
            self._log(f'Calculate outer branches: {root}')
        outer_branches, seen = [], set()
        frontier = collections.deque([root])
        while len(frontier) > 0:
            # breadth first search
            c = frontier.popleft()
            if c in seen:
                continue
            seen.add(c)
            dep = self._depended[c]
            if dep:
                frontier.extend(dep)
            else:
                outer_branches.append(c)
        return outer_branches

    def _update(self, name):
        if self._verbose:
            self._log(f'Update: {name}')
        outer_branches = self._calculate_outer_branches(name)
        for other in outer_branches:
            # we use a call to getattr to trigger a compute + cache
            self.__getattr__(other)

    def __delattr__(self, name):
        if self._verbose:
            self._log(f'Del attr: {name}')
        self._invalidate_cache_depends(name)
        del self._vals[name]

    def __dir__(self):
        if self._verbose:
            self._log('Dir')
        return list(self._vals.keys())

    __getitem__ = __getattr__
    __setitem__ = __setattr__
    __delitem__ = __delattr__

    def __call__(self, function, *args, **kwargs):
        if self._verbose:
            self._log(f'Call')
        required_args = [x for x in inspect.getfullargspec(function)[0] if
                         x != 'self']
        required_args = required_args[len(args):]
        required_args = [x for x in required_args if not x in kwargs]
        kwargs = {**kwargs, **{x: x for x in required_args}}
        getter = lambda x: ReactiveGetter(self, x) if isinstance(x, str) else x
        args = [getter(x) for x in args]
        kwargs = {k: getter(v) for k, v in kwargs.items()}
        return ReactiveOp(function, '', *args, **kwargs)


class ReactiveObject:

    def _get_depends(self):
        raise NotImplementedError

    def _compute(self):
        raise NotImplementedError


class ReactiveGetter(ReactiveObject):
    def __init__(self, obj, name):
        self._obj = obj
        self._name = name

    def _get_depends(self):
        return set([(self._obj, self._name)])

    def _compute(self):
        return getattr(self._obj, self._name)


class ReactiveOp(ReactiveObject):
    def __init__(self, obj, call, *args, **kwargs):
        self._obj = obj
        self._call = call
        self._args = args
        self._kwargs = kwargs

    def _get_depends(self):
        depends = set()
        for o in itertools.chain(self._args,
                                 self._kwargs.values(),
                                 [self._obj]):
            if isinstance(o, ReactiveObject):
                depends |= o._get_depends()
        return depends

    def _compute(self):
        comp = lambda x: x._compute() if isinstance(x, ReactiveObject) else x
        args = [comp(x) for x in self._args]
        kwargs = {k: comp(v) for k, v in self._kwargs.items()}
        obj = comp(self._obj)
        if self._call == '':
            return obj(*args, **kwargs)
        else:
            return getattr(obj, self._call)(*args, **kwargs)
