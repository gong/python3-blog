import functools
import inspect
import asyncio,os
from apis import APIError
import logging;logging.basicConfig(level=logging.INFO)
from urllib import parse
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
def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found
class RequestHandler(object):#url处理函数适配器

    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)


    @asyncio.coroutine
    def __call__(self, request):
        print('***********************'+request.path)
        kw=None
        if request.method=='POST':
            if not request.content_type:
                return web.HTTPBadRequest('丢失了Content-type')
            ct=request.content_type.lower()
            if ct.startswith('application/json'):
                params=yield from request.json()
                if not isinstance(params,dict):
                    return web.HTTPBadRequest('Json 格式错误')
                kw=params
            elif ct.startswith('application/xx-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                params=yield from request.post()#获取来自浏览器的值
                kw=dict(**params)
            else:
                return web.HTTPBadRequest('不支持的Content-type:%s'%request.content_type)
        if request.method=='GET':
            qs=request.query_string
            if qs:
                kw=dict()
                for k,v in parse.parse_qs(qs,True).items():
                    kw[k]=v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
            # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = yield from self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

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
    app.router.add_route(method, path, RequestHandler(app, fn))#绑定处理器函数 中间件中的handler(request)会调用RequestHandler(app,fn)
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


