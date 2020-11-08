
import collections
import inspect
import itertools
import pathlib
import threading
import time

try:
    import ipywidgets
except ModuleNotFoundError:
    pass

try:
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.animation
except ModuleNotFoundError:
    pass

def _check_module_imported(name):
    if not name in locals():
        raise Exception("This functionality is not available without " + name)

### Be warned. Some of the components of this library are experimental and
### not thread safe.

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
        self._clear_cache()

    def _clear_cache(self):
        s = super().__setattr__
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

    def _recalculate(self, name):
        if self._verbose:
            self._log(f'Recalculate: {name}')
        self._invalidate_cache_depends(name)
        if not self._lazy_eval:
            outer_branches = self._calculate_outer_branches(name)
            for other in outer_branches:
                # we use a call to getattr to trigger a compute + cache
                self.__getattr__(other)

    def _to_getter(self, value):
        if isinstance(value, str):
            return Getter(self, value)
        return value

    def _register_update_hook(self, name, value):
        def hook():
            self._recalculate(name)
        value.register_update_hook(id(self), hook)

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
            # there is currently no reason that the
            # calculation of dep and val could not be
            # merged
            dep = val.get_depends()
            val = val.compute()
            self._update_cache(name, val)
            self._update_depends(name, dep)
        return val

    def __setattr__(self, name, value):
        if self._verbose:
            self._log(f'Set attr: {name}')
        self._vals[name] = value
        if isinstance(value, ReactiveObjectWithArgs):
            value.convert_string_to_getters(self._to_getter)
        if isinstance(value, UpdateHookMixin):
            self._register_update_hook(name, value)
        self._recalculate(name)

    def __delattr__(self, name):
        if self._verbose:
            self._log(f'Del attr: {name}')
        self._invalidate_cache_depends(name)
        del self._vals[name]

    def __contains__(self, name):
        return name in self._vals

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
        return Op(function, *args, **kwargs)

    def context(self, **kwargs):
        return ReactiveContext(self, **kwargs)

    def update(self, other):
        for k, v in other.items():
            self[k] = v

    def get(self, name, default=None):
        try:
            return self[name]
        except AttributeError:
            return default

    def items(self):
        for name in dir(self):
            yield name, self[name]

class ReactiveContext:
    def __init__(self, reactive__, **kwargs):
        self._reactive = reactive__
        self._kwargs = kwargs

    def __enter__(self):
        self._existing_kwargs = {
            k: self._reactive._vals[k]
            for k in self._kwargs
            if k in self._reactive._vals
        }
        for k, v in self._kwargs.items():
            self._reactive.__setattr__(k, v)

    def __exit__(self, type, value, traceback):
        for k, v in self._existing_kwargs.items():
            self._reactive.__setattr__(k, v)
        for k in [k for k in self._kwargs if not k in self._existing_kwargs]:
            self._reactive.__delattr__(k)

class ReactiveObject:

    def __init__(self):
        super().__init__()

    def get_depends(self):
        raise NotImplementedError

    def compute(self):
        raise NotImplementedError


class ReactiveObjectWithArgs(ReactiveObject):

    def __init__(self):
        super().__init__()
        self._args = []
        self._kwargs = {}
        self._extra_args = {}
        self._converted = False

    def _check_converted(self):
        if not self._converted:
            raise Exception("Reactive object has not been registered"
                            " with a Reactive base")

    def convert_string_to_getters(self, convert_function):
        self._args = [convert_function(x)
                     for x in self._args]
        self._kwargs = {k:convert_function(v) for
                       k,v in self._kwargs.items()}
        self._extra_args = {k:convert_function(v)
                           for k,v in self._extra_args.items()}
        self._converted = True

    def get_depends(self):
        self._check_converted()
        depends = set()
        for o in itertools.chain(self._args,
                                 self._kwargs.values(),
                                 self._extra_args.values()):
            if isinstance(o, ReactiveObject):
                depends |= o.get_depends()
        return depends

    def _compute_value(self, value):
        if isinstance(value, ReactiveObject):
            return value.compute()
        return value

    def _compute_args(self):
        args = [self._compute_value(x)
                for x in self._args]
        kwargs = {k: self._compute_value(v)
                  for k, v in self._kwargs.items()}
        extra_args = {k: self._compute_value(v)
                      for k, v in self._extra_args.items()}
        return args, kwargs, extra_args

    def compute(self):
        self._check_converted()
        args, kwargs, extra_args = self._compute_args()
        return self.compute_raw(args, kwargs, extra_args)

    def compute_raw(self, args, kwargs, extra_args):
        raise NotImplementedError

class UpdateHookMixin:

    def __init__(self):
        super().__init__()
        self._hooks = {}

    def register_update_hook(self, id_, function):
        self._hooks[id_] = function

    def trigger_update_hooks(self):
        for name, function in self._hooks.items():
            function()


class Getter(ReactiveObject):
    def __init__(self, obj, name):
        super().__init__()
        self._obj = obj
        self._name = name

    def get_depends(self):
        return set([(self._obj, self._name)])

    def compute(self):
        return getattr(self._obj, self._name)


def _fill_kwargs(function, args, kwargs, ignore=['self']):
    if not isinstance(function, str):
        required_args = [x for x in inspect.getfullargspec(function)[0]
                         if x not in ignore]
        required_args = required_args[len(args):]
        required_args = [x for x in required_args if not x in kwargs]
        kwargs = {**kwargs, **{x: x for x in required_args}}
    return kwargs


class Op(ReactiveObjectWithArgs):
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        kwargs = _fill_kwargs(function, args, kwargs)
        self._args += args
        self._kwargs = {**self._kwargs, **kwargs}
        self._extra_args = {**self._extra_args, **{'function': function}}

    def compute_raw(self, args, kwargs, extra_args):
        function = extra_args['function']
        return function(*args, **kwargs)

class FileData(ReactiveObject, UpdateHookMixin):
    def __init__(self, path, sleep=1):
        super().__init__()
        self.value = None
        self.path = pathlib.Path(path)
        self.sleep = sleep
        self.update_time = None
        self._update()
        self.thread = threading.Thread(target=self._thread_method)
        self.alive = True
        self.thread.start()

    def _thread_method(self):
        while self.alive:
            time.sleep(self.sleep)
            self._update()

    def _update(self):
        file_update_time = self.path.stat().st_mtime
        if self.update_time is None or self.update_time < file_update_time:
            with open(self.path, 'rb') as f:
                self.value = f.read()
            self.update_time = file_update_time
            self.trigger_update_hooks()

    def __del__(self):
        self.alive = False

    def get_depends(self):
        return set()

    def compute(self):
        return self.value

class Interact(ReactiveObject, UpdateHookMixin):
    def __init__(self, label, params):
        _check_module_imported('ipywidgets')
        super().__init__()
        self.value = None
        self.widget_factory = ipywidgets.interact(
            self._update, value=params
        )
        self.widget = self.widget_factory.widget.kwargs_widgets[0]
        self.widget.description = label

    def _update(self, value):
        self.value = value
        self.trigger_update_hooks()

    def get_depends(self):
        return set()

    def compute(self):
        return self.value


class Plot(Op):
    def __init__(self, plot_fn, *args, ax=None, init_fn=None, **kwargs):
        _check_module_imported('matplotlib')
        kwargs = _fill_kwargs(plot_fn, args, kwargs, ignore=['ax'])
        if ax is None:
            fig, ax = plt.subplots()
        if init_fn is not None:
            init_fn(ax=ax)
        self.ax = ax
        def update_fn(*args, **kwargs):
            self._before_plot(ax)
            r = plot_fn(ax=self.ax, *args, **kwargs)
            self._after_plot(ax)
            return ax
        super().__init__(update_fn, *args, **kwargs)

    def _before_plot(self, ax):
        [l.remove() for l in ax.lines]
        [l.remove() for l in ax.patches]
        ax.set_prop_cycle(None)

    def _after_plot(self, ax):
        ax.relim()

class Output(Op):
    def __init__(self, output_fn, *args, **kwargs):
        _check_module_imported('ipywidgets')
        kwargs = _fill_kwargs(output_fn, args, kwargs, ignore=['self'])
        self.widget = ipywidgets.Output()
        self.lock = threading.Lock()

        def update_fn(*args, **kwargs):
            with self.lock:
                r = output_fn(*args, **kwargs)
                self.widget.clear_output() # why doesnt wait=True work?
                self.widget.append_stdout(str(r))
            return self.widget
        super().__init__(update_fn, *args, **kwargs)
