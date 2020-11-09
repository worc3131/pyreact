# reactpy

WARNING: This library is not thread safe. Input and output components (FileData, 
Interact and Plot) are experimental

A simple implementation of a reactive environment, with caching, in Python (in 
the style of kdb views). It assumes that functions do not have side effects. 
Evaluation is lazy i.e. values are only calculated when needed. The cache and 
lazy evaluation can be disabled if needed.

Interactive examples: https://mybinder.org/v2/gh/worc3131/reactpy_examples/HEAD

```
from reactpy import Reactive
r = Reactive()
r.a, r.b = 3, 5
r.c = r(lambda a, b: a*b)
r.c  # 15 = 3*5
r.a = 7 

r.c  # 35 = 7*5 <- c has been updated reactively !!
```

We create a reactive environment as `r = Reactive()`, we can then assign to this
static values as `r.a = 3` or reactive values as `r.b = r(lambda a: 2*a)`. Getting
`r.a` or `r.b` gives 3 and 6 respectively. `r['a']` and `r['a'] = 3` are also
available if needed (as in the style of javascript).

The arguments for the reactive function / callable can either be implied from 
the name of the callables arguments or can be specified with names or constants,
as args, kwargs or both.

```
r = Reactive()
r.a = 3
r.b = 5
r.c = r(lambda a, b: a*b)
r.c  # 15 = 3*5
r.d = r(lambda x, y: x+y, 'a', 10)
r.d  # 8 = 3+10
r.e = r(lambda x, y: x-y, y='b', x='a')
r.e  # -2 = 3-5
r.f = r(lambda x, y: x/y, 'a', y='b')
r.f  # 0.6 = 3/5

r.a = 10
r.f  # 2.0 = 10/5
``` 

Callables need not be lambdas, functions, classes or any callable are acceptable.

```
r = Reactive()
r.a = 3
r.b = 5

def f(a, b):
    return a+b
r.c = r(f)
r.c  # 8 = 3+5

class T:
    def __init__(self, a):
        self.x = a
r.d = r(T)
r.d.x  # 3

r.a = 10
r.d.x  # 10
```

Using this framework we can cleanly create an interactive plot, with widget
sliders as inputs and a plot that updates.
```
from reactpy import Reactive, Interact, Plot

import numpy as np
import pandas as pd
%matplotlib widget 

r = Reactive(lazy_eval=False)
for k in 'abcd':
    r[k] = Interact(k, (-1, 5, 0.01))
r.space_max, r.space_step = 10*np.pi, 2000
r.space = r(lambda mn, mx, st: np.linspace(mn, mx, st), 0, 'space_max', 'space_step')
r.x = r(lambda s,a,b: np.sin(s*a)*np.cos(s*b), s='space')
r.y = r(lambda s,c,d: np.sin(s*c)*np.cos(s*d), s='space')
r.plot = Plot(lambda ax, x, y: ax.plot(x, y, color='red'))
```

# Installation

1. Clone this repository and enter it
2. Type `pip install .` to install it

This framework could be extended if it proves useful. Let me know if you would
like me to add it to pypi / conda.
