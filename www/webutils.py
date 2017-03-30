import functools
import inspect
import asyncio,os
import logging;logging.basicConfig(level=logging.INFO)
from aiohttp import web
def get(path):
    #Define decorator @get('/path')
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args,**kw):
            return func(*args,**kw)
        # wrapper.__name__ = func.__name__#这里不需要这行代码 functools.wraps(func)就起到了将函数名转换为被装饰的函数名
        wrapper.__method__='GET'
        wrapper.__route__=path
        return wrapper
    return decorator
def post(path):
    #Define decorator @post('/path')
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args,**kw):
            return func(*args,**kw)
        #wrapper.__name__ = func.__name__#这里不需要这行代码 functools.wraps(func)就起到了将函数名转换为被装饰的函数名
        wrapper.__method__='POST'
        wrapper.__route__=path
        return wrapper
    return decorator
class RequestHandler(object):#url处理函数适配器

    def __init__(self, app, fn):
        self._app = app
        self._func = fn


    @asyncio.coroutine
    def __call__(self, request):
        kw = request
        r = yield from self._func(**kw)#返回了一个协程函数
        return r

def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)#如果fn不是协程就将它转换为协程函数
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))
def add_routes(app, module_name):#自动注册handlers模块所有的函数
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())#导入模块
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):#返回对象的所有属性
        if attr.startswith('_'):#检查是不是内部方法
            continue
        fn = getattr(mod, attr)
        if callable(fn)and hasattr(fn,'__method__')and hasattr(fn,'__route__'):
            add_route(app, fn)


