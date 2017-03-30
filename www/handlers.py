from aiohttp import web
#from app import get#循环导入导致AttributeError错误
from webutils import get,post
from mymodel import User,Blog,next_id
from apis import APIError,APIValueError
import json
import hashlib
import re,time
from config import configs
COOKIE_NAME = 'webappsession'
_COOKIE_KEY = configs.session.secret

def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

@get('/')
def index():#为了实现web server 必须创建request handler 它可能是函数也可能是协程
    blogs = yield from Blog.findAll()
    return {
        '__template__':'blogs.html',
        'blogs':blogs
    }
@get('/api/comments')
def api_comments(*, page='1'):
    pass
@get('/blog/{id}')
def get_blog(id):
    pass
@get('/signin')
def signin():
    return {
        '__template__':'login.html'
    }
@post('/signin')
def signin_form():
    pass
@get('/api/users')
def api_get_users():
    num = yield from User.findNumber('count(id)')
    if num == 0:
        return dict(users=())
    users = yield from User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    return dict(users=users)

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@post('/api/users')
def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = yield from User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r