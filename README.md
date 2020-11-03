# reactpy

A simple implementation of a reactive environment with caching in Python, in the
style of kdb views. It assumes that functions do not have side effects. 
Evaluation is lazy i.e. values are only calculated when needed. The cache and 
lazy evaluation can be disabled if needed.

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

A more advanced example:

```
import numpy as np
import pandas as pd
import matplotlib.pylab as plt
%matplotlib auto 
plt.ioff()
def plot(x, y):
    fig, ax = plt.subplots()
    ax.plot(x, y)
    return fig

r = Reactive()
r.a, r.b, r.c, r.d = 1, 0.5, 2, 1
r.space_max, r.space_step = 2*np.pi, 200
r.space = r(lambda mn, mx, st: np.linspace(mn, mx, st), 0, 'space_max', 'space_step')
r.x = r(lambda s,a,b: np.sin(s*a)*np.cos(s*b), s='space')
r.y = r(lambda s,c,d: np.sin(s*c)*np.cos(s*d), s='space')
r.plot = r(plot)
r.plot.show()

r.a = 2
r.plot.show()

fig, ax = plt.subplots(3,3)
for i in range(3):
    for j in range(3):
        r.a, r.b = 1+i, 1+j  # update model
        ax[i][j].plot(r.x, r.y)  # plot new results
        ax[i][j].set_title(f'a={r.a} b={r.b}')
fig.show()
```

# Installation

1. Clone this repository and enter it
2. Type `pip install .` to install it

This framework could be extended if it proves useful. Let me know if you would
like me to add it to pypi / conda.
