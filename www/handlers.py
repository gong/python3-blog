from aiohttp import web
#from app import get#循环导入导致AttributeError错误
from webutils import get,post
from mymodel import User,Blog,next_id
from apis import APIError,APIValueError,Page
import json
import hashlib
import re,time
from config import configs
import logging
logging.basicConfig(level=logging.INFO)
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

# 解密cookie:

async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

@get('/')
async def index(request):#为了实现web server 必须创建request handler 它可能是函数也可能是协程
    blogs = await Blog.findAll()
    return {
        '__template__':'blogs.html',
        'blogs':blogs,
        'user':request.__user__
    }
@get('/api/comments')
def api_comments(*, page='1'):
    pass
@get('/blog/{id}')
async def get_blog(id,request):
    blog=await Blog.find(id)
    if blog is not None:
        return {
            '__template__':'blog_view.html',
            'blog':blog,
            'user':request.__user__
        }
    else:
        return {
            '__template__':'404.html'
        }
@get('/api/blog/{id}')
async def get_api_blog(id):
    blog=await Blog.find(id)
    return {
        'name':blog.name,
        'summary': blog.summary,
        'content': blog.content,
    }

@get('/signin')
def signin():
    return {
        '__template__':'login.html'
    }
@get('/signout')
async def signout():
    blogs = await Blog.findAll()
    r = web.Response()
    r.del_cookie(COOKIE_NAME)
    return {
        '__template__': 'blogs.html',
        'blogs':blogs
    }
# @get('/api/users')
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
async def api_register_user(*, email, name, passwd):
    print('-------------------------------------------')
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        logging.warning("用户存在")
        raise APIError('register:failed', 'email', '邮箱已经被注册')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r
@get('/register')
async def api_register():
    return {
        '__template__':'register.html'
    }

@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', '密码错误')
    if not passwd:
        raise APIValueError('passwd', '密码错误')
    users =await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', '邮箱不存在')
    user = users[0]
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', '密码错误')
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r
@get('/api/blogs')
def api_blogs(*, page=1,request):
    page_index = page
    num = yield from Blog.findNumber('count(id)')
    p = Page(num, int(page_index))
    if num == 0:
        return dict(page=p, blogs=())
    if request.__user__.admin:
        blogs = yield from Blog.findAll(orderBy='created_at desc',limit=(p.offset, p.limit))
    else:
        blogs = yield from Blog.findAll(where='user_id=?',args=[request.__user__.id,],orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)
@get('/manage/blogs')
def manage_blogs(*,request):
    return {
        '__template__': 'manage_blogs.html',
        'page_index':1,
        'user':request.__user__
    }
@get('/manage/blogs/edit')
async def edit_blog(id,request):
    blog=await Blog.find(id)
    return {
        '__template__':'edit_blog.html',
        'user':request.__user__,
        'id':id,
    }
@get('/manage/blogs/create')
async def create_blog(request):
    return {
        '__template__':'create_blog.html',
        'user':request.__user__
    }
@post('/manage/blogs/edit')
async def edit_save(*,id,content,summary,name):
    blog=await Blog.find(id)
    if blog is not None:
        blog.summary=summary
        blog.content=content
        blog.name=name
        await blog.update()
        return '200'
    else:
        return '200'
@post('/api/blogs/{id}/delete')
async def delete_blog(id):
    blog=await Blog.find(id)
    if blog is not None:
        await blog.remove()
        return '200'
    else:
        return '200'
@post('/manage/blogs/create')
async def create_blog_save(content,summary,name,request):
    id=next_id()
    user=request.__user__
    blog=Blog(id=id,content=content,summary=summary,name=name,user_name=user.name,user_image=user.image,user_id=user.id)
    await blog.save()
    return '200'